/* Own-process synthetic GO supervisor probe. NO radio/exec/service/storage API.
 * Exercises deadlines/output bounds/cancel/reap through select, not legacy poll.
 * This is not a scan worker and does not prove descendant containment or native
 * driver cancellation. Do not deploy/run natively without separate probe review.
 */
#define _POSIX_C_SOURCE 200809L
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/select.h>
#include <sys/stat.h>
#include <sys/prctl.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define OUTPUT_LIMIT 65536UL
#define WORK_MS 1000LL
#define TERM_MS 200LL
#define REAP_MS 400LL
static volatile sig_atomic_t cancelled=0;
static void cancel(int signum) { (void)signum;cancelled=1; }

static long long now_ms(void)
{
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC,&now)) return -1;
    return (long long)now.tv_sec*1000+now.tv_nsec/1000000;
}

#ifndef GO_WORKER_RUN
static void nap(long millis)
{
    struct timespec delay={millis/1000,(millis%1000)*1000000};
    while (nanosleep(&delay,&delay) && errno==EINTR) {}
}

static void synthetic(const char *mode)
{
    char block[4096];
    memset(block,'S',sizeof(block));
    if (!strcmp(mode,"ignore-term")) signal(SIGTERM,SIG_IGN);
    if (!strcmp(mode,"hang") || !strcmp(mode,"ignore-term")) {
        for (;;) pause();
    }
    if (!strcmp(mode,"flood")) {
        for (;;) {
            ssize_t n=write(STDOUT_FILENO,block,sizeof(block));
            if (n<0 && errno==EINTR) continue;
            if (n<=0) _exit(8);
        }
    }
    if (!strcmp(mode,"late-output")) {
        nap(700);if (write(STDOUT_FILENO,block,128)!=128) _exit(8);
        nap(700);_exit(0);
    }
    if (!strcmp(mode,"nonzero")) _exit(9);
    if (write(STDOUT_FILENO,block,128)!=128) _exit(8);
    _exit(0);
}
#define GO_WORKER_RUN(mode) synthetic(mode)
#endif
#ifndef GO_ACTION
#define GO_ACTION "--probe"
#define GO_CONTROL_ACTION "--probe-controlled"
#define GO_VALID_MODE(mode) (!strcmp(mode,"normal") || !strcmp(mode,"flood") || !strcmp(mode,"hang") || !strcmp(mode,"ignore-term") || !strcmp(mode,"late-output") || !strcmp(mode,"nonzero"))
#endif
#ifndef GO_WORKER_PREPARE
#define GO_WORKER_PREPARE() 0
#endif

int main(int argc,char **argv)
{
    int output[2],flags,status=0,reaped=0,eof=0,result=0,phase=0;
    int controlled,control_flags=-1;
    char control[5];size_t control_used=0;
    pid_t child,parent=getpid();
    unsigned long bytes=0;
    long long start,deadline,now;
    const char *reason="completed";
    struct sigaction action;
    struct stat control_info;
    if (argc!=3 || (strcmp(argv[1],GO_ACTION) && strcmp(argv[1],GO_CONTROL_ACTION)) ||
        !GO_VALID_MODE(argv[2]) || GO_WORKER_PREPARE()) return 2;
    controlled=!strcmp(argv[1],GO_CONTROL_ACTION);
    if (controlled) {
        if (fstat(STDIN_FILENO,&control_info) || (!S_ISFIFO(control_info.st_mode) && !S_ISSOCK(control_info.st_mode))) return 2;
        control_flags=fcntl(STDIN_FILENO,F_GETFL);
        if (control_flags<0 || fcntl(STDIN_FILENO,F_SETFL,control_flags|O_NONBLOCK)) return 4;
    }
    memset(&action,0,sizeof(action));action.sa_handler=cancel;sigemptyset(&action.sa_mask);
    if (sigaction(SIGTERM,&action,NULL) || sigaction(SIGHUP,&action,NULL) ||
        sigaction(SIGINT,&action,NULL) || signal(SIGPIPE,SIG_IGN)==SIG_ERR) return 4;
    start=now_ms();if (start<0 || pipe(output)) return 4;
    if (output[0]>=FD_SETSIZE) {close(output[0]);close(output[1]);return 4;}
    flags=fcntl(output[0],F_GETFL);
    if (flags<0 || fcntl(output[0],F_SETFL,flags|O_NONBLOCK)) {close(output[0]);close(output[1]);return 4;}
    child=fork();
    if (child<0) {close(output[0]);close(output[1]);return 4;}
    if (!child) {
        /* Linux own-child guard; check parent again to close the fork/prctl
         * race. No promise about grandchildren or kernel driver scan state. */
        if (prctl(PR_SET_PDEATHSIG,SIGKILL) || getppid()!=parent) _exit(8);
        signal(SIGTERM,SIG_DFL);signal(SIGHUP,SIG_DFL);signal(SIGINT,SIG_DFL);
        close(output[0]);
        if (dup2(output[1],STDOUT_FILENO)<0) _exit(8);
        close(output[1]);close(STDIN_FILENO);close(STDERR_FILENO);
        GO_WORKER_RUN(argv[2]);_exit(8);
    }
    close(output[1]);deadline=start+WORK_MS;
    for (;;) {
        char block[4096];
        ssize_t count;
        pid_t waited;
        now=now_ms();
        if (now<0) {reason="clock_failed";result=4;now=deadline;}
        if (controlled && !phase && !result) {
            count=read(STDIN_FILENO,control+control_used,sizeof(control)-control_used);
            if (count>0) {
                control_used+=(size_t)count;
                if (memcmp(control,"STOP\n",control_used)) {reason="control_refused";result=8;}
                else if (control_used==sizeof(control)) {reason="control_stop";result=7;}
            } else if (!count) {
                reason=control_used?"control_refused":"control_closed";result=control_used?8:7;
            } else if (errno!=EAGAIN && errno!=EWOULDBLOCK && errno!=EINTR) {
                reason="control_failed";result=4;
            }
        }
        /* One bounded read per iteration: a hot writer cannot starve timers. */
        if (!eof) {
            count=read(output[0],block,sizeof(block));
            if (count>0) {
                if ((unsigned long)count>OUTPUT_LIMIT-bytes) {
                    if (!result) {reason="output_limit";result=6;}
                }
                else bytes+=(unsigned long)count;
            } else if (!count) eof=1;
            else if (errno!=EAGAIN && errno!=EWOULDBLOCK && errno!=EINTR) {
                reason="read_failed";result=4;
            }
        }
        if (!reaped) {
            waited=waitpid(child,&status,WNOHANG);
            if (waited==child) reaped=1;
            else if (waited<0 && errno!=EINTR) {reason="reap_unconfirmed";result=4;break;}
        }
        if (!phase) {
            if (cancelled) {reason="cancelled";result=7;}
            else if (now>=deadline && !(reaped && eof)) {reason="timeout";result=3;}
            if (result) {
                if (!reaped && kill(child,SIGTERM) && errno!=ESRCH) {reason="signal_failed";result=4;}
                phase=1;deadline=now+TERM_MS;
            }
        }
        if (reaped && eof) break;
        if (phase==1 && now>=deadline) {
            if (!reaped && kill(child,SIGKILL) && errno!=ESRCH) {reason="signal_failed";result=4;}
            phase=2;deadline=now+REAP_MS;
        } else if (phase==2 && now>=deadline) {
            reason="drain_unconfirmed";result=4;break;
        }
        {
            fd_set ready;
            struct timeval delay={0,10000};
            int selected;
            FD_ZERO(&ready);if (!eof) FD_SET(output[0],&ready);
            if (controlled && !phase) FD_SET(STDIN_FILENO,&ready);
            selected=select(eof?(controlled && !phase?1:0):output[0]+1,&ready,NULL,NULL,&delay);
            if (selected<0 && errno!=EINTR) {reason="select_failed";result=4;}
        }
    }
    close(output[0]);
    if (control_flags>=0 && fcntl(STDIN_FILENO,F_SETFL,control_flags)) {reason="control_flags_unconfirmed";result=4;}
#ifdef GO_WORKER_DIAGNOSTICS
    if (reaped && WIFEXITED(status) && WEXITSTATUS(status))
        fprintf(stderr,"Fixture worker exit=%d\n",WEXITSTATUS(status));
#endif
    if (!result && (!WIFEXITED(status) || WEXITSTATUS(status)!=0)) {reason="worker_failed";result=5;}
    printf("GO-SUPERVISOR=OBSERVED result=%s bytes=%lu child_reaped=%s pipe_drained=%s descendant_containment_verified=no native_scan_verified=no\n",
           reason,bytes,reaped?"yes":"no",eof?"yes":"no");
    return result;
}
