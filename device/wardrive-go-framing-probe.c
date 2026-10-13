/* Stdin-pipe framing probe only. Never parses JSON, authenticates, forks,
 * executes commands, binds a listener or opens a supplied file/path.
 * Payloads are discarded, not reflected or logged. Native run needs review.
 */
#define _POSIX_C_SOURCE 200809L
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/select.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>
#include "wardrive-go-framing.h"

static volatile sig_atomic_t cancelled=0;
static void cancel(int signal_number) { (void)signal_number;cancelled=1; }
static long long now_ms(void)
{
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC,&now)) return -1;
    return (long long)now.tv_sec*1000+now.tv_nsec/1000000;
}

int main(int argc,char **argv)
{
    go_frames frames;
    go_frame_batch batch;
    unsigned char input[GO_FRAME_CHUNK];
    unsigned long total_bytes=0,payload_bytes=0;
    unsigned int accepted=0,index;
    int original_flags,result=0;
    long long started,now;
    const char *reason="framed";
    struct stat info;
    struct sigaction action;
    if (argc!=2 || strcmp(argv[1],"--probe-frames")) return 2;
    if (fstat(STDIN_FILENO,&info) || (!S_ISFIFO(info.st_mode) && !S_ISSOCK(info.st_mode))) return 2;
    started=now_ms();if (started<0) return 4;
    original_flags=fcntl(STDIN_FILENO,F_GETFL);
    if (original_flags<0 || fcntl(STDIN_FILENO,F_SETFL,original_flags|O_NONBLOCK)) return 4;
    memset(&action,0,sizeof(action));action.sa_handler=cancel;sigemptyset(&action.sa_mask);
    if (sigaction(SIGTERM,&action,NULL) || sigaction(SIGHUP,&action,NULL) || sigaction(SIGINT,&action,NULL)) {
        (void)fcntl(STDIN_FILENO,F_SETFL,original_flags);return 4;
    }
    go_frames_init(&frames);memset(&batch,0,sizeof(batch));
    for (;;) {
        ssize_t bytes;
        now=now_ms();
        if (cancelled) {reason="cancelled";result=7;break;}
        if (now<0) {reason="clock_unconfirmed";result=4;break;}
        if (now-started>=1000) {reason="timeout";result=3;break;}
        bytes=read(STDIN_FILENO,input,sizeof(input));
        if (bytes>0) {
            total_bytes+=(unsigned long)bytes;
            if (total_bytes>(unsigned long)GO_FRAME_TOTAL*GO_FRAME_CHUNK) {
                reason="input_limit";result=6;break;
            }
            if (go_frames_feed(&frames,input,(size_t)bytes,&batch)) {reason="refused";result=5;break;}
            accepted+=batch.count;
            for (index=0;index<batch.count;index++) payload_bytes+=(unsigned long)batch.length[index];
            memset(&batch,0,sizeof(batch));continue;
        }
        if (!bytes) {
            if (go_frames_finish(&frames)) {reason="truncated";result=5;}
            break;
        }
        if (errno!=EAGAIN && errno!=EWOULDBLOCK && errno!=EINTR) {reason="read_unconfirmed";result=4;break;}
        {
            fd_set ready;
            struct timeval wait={0,10000};
            FD_ZERO(&ready);FD_SET(STDIN_FILENO,&ready);
            if (select(1,&ready,NULL,NULL,&wait)<0 && errno!=EINTR) {reason="select_unconfirmed";result=4;break;}
        }
    }
    if (result) (void)go_frames_refuse(&frames,&batch);
    memset(input,0,sizeof(input));memset(&batch,0,sizeof(batch));
    if (fcntl(STDIN_FILENO,F_SETFL,original_flags)) {reason="flags_unconfirmed";result=4;}
    printf("GO-FRAMING=OBSERVED result=%s frames=%u payload_bytes=%lu auth_verified=no native_go_verified=no\n",
           reason,accepted,payload_bytes);
    return result;
}
