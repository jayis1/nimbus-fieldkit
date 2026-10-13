/* Inert native compatibility probe: own pipes/one child and /proc/self/fd only.
 * No device reads, remounts, service control, exec, sockets or file creation.
 * Owner-approved temporary staging is separate from execution of this binary.
 */
#define _POSIX_C_SOURCE 200809L
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/select.h>
#include <sys/wait.h>
#include <dirent.h>
#include <poll.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t notified;
static void notify(int signum) { (void)signum; notified=1; }

static int receive_byte(int fd, unsigned char wanted)
{
    struct timespec start, now;
    if (clock_gettime(CLOCK_MONOTONIC,&start)) return -1;
    for (;;) {
        fd_set reads;
        struct timeval delay={0,100000};
        unsigned char byte;
        int ready;
        if (clock_gettime(CLOCK_MONOTONIC,&now) || now.tv_sec-start.tv_sec>=3) return -1;
        FD_ZERO(&reads);FD_SET(fd,&reads);
        ready=select(fd+1,&reads,NULL,NULL,&delay);
        if (ready<0 && errno==EINTR) continue;
        if (ready<0) return -1;
        if (!ready) continue;
        if (read(fd,&byte,1)!=1 || byte!=wanted) return -1;
        return 0;
    }
}

int main(int argc,char **argv)
{
    int event[2]={-1,-1}, broken[2]={-1,-1}, status=0, result=1;
    pid_t child=-1, ended;
    struct timespec first, second;
    struct stat st;
    struct sigaction action;
    struct pollfd peer;
    DIR *directory;
    struct dirent *entry;
    int enumerated=0, flags;
    if (argc!=2 || strcmp(argv[1],"--probe")) return 2;
    if (clock_gettime(CLOCK_MONOTONIC,&first) || clock_gettime(CLOCK_MONOTONIC,&second) ||
        second.tv_sec<first.tv_sec || (second.tv_sec==first.tv_sec && second.tv_nsec<first.tv_nsec)) goto finish;
    puts("monotonic=PASS");
    directory=opendir("/proc/self/fd");
    if (!directory) goto finish;
    errno=0;
    while ((entry=readdir(directory))) if (!strcmp(entry->d_name,"0")) enumerated=1;
    if (errno) enumerated=0;
    closedir(directory);
    if (!enumerated) goto finish;
    puts("self_fd_enumeration=PASS");
    if (pipe(broken) || broken[1]>=FD_SETSIZE || fstat(broken[1],&st) || !S_ISFIFO(st.st_mode)) goto finish;
    close(broken[0]);broken[0]=-1;
    peer.fd=broken[1];peer.events=0;peer.revents=0;
    if (poll(&peer,1,0)!=1 || !(peer.revents&POLLERR)) goto finish;
    close(broken[1]);broken[1]=-1;
    puts("pipe_peer_loss_poll=PASS");
    if (pipe(event) || event[0]>=FD_SETSIZE || event[1]>=FD_SETSIZE) goto finish;
    flags=fcntl(event[0],F_GETFL);
    if (flags<0 || fcntl(event[0],F_SETFL,flags|O_NONBLOCK)) goto finish;
    memset(&action,0,sizeof(action));action.sa_handler=SIG_DFL;sigemptyset(&action.sa_mask);
    if (sigaction(SIGCHLD,&action,NULL)) goto finish;
    child=fork();
    if (child<0) goto finish;
    if (!child) {
        struct timespec began, now;
        close(event[0]);
        if (setsid()<0 || getsid(0)!=getpid() || getpgrp()!=getpid()) _exit(10);
        memset(&action,0,sizeof(action));action.sa_handler=notify;sigemptyset(&action.sa_mask);
        if (sigaction(SIGUSR1,&action,NULL) || sigprocmask(SIG_SETMASK,&action.sa_mask,NULL) ||
            clock_gettime(CLOCK_MONOTONIC,&began)) _exit(11);
        if (write(event[1],"R",1)!=1) _exit(12);
        while (!notified) {
            struct timeval delay={0,100000};
            if (clock_gettime(CLOCK_MONOTONIC,&now) || now.tv_sec-began.tv_sec>=3) _exit(14);
            if (select(0,NULL,NULL,NULL,&delay)<0 && errno!=EINTR) _exit(15);
        }
        if (write(event[1],"S",1)!=1) _exit(13);
        close(event[1]);_exit(0);
    }
    close(event[1]);event[1]=-1;
    if (receive_byte(event[0],'R') || getsid(child)!=child || getpgid(child)!=child) goto finish;
    puts("detached_child_session=PASS");
    ended=waitpid(child,&status,WNOHANG);
    if (ended==child) { child=-1;goto finish; }
    if (ended<0 || kill(child,SIGUSR1) || receive_byte(event[0],'S')) goto finish;
    puts("own_child_signal_and_select=PASS");
    do { ended=waitpid(child,&status,0); } while (ended<0 && errno==EINTR);
    if (ended!=child) goto finish;
    child=-1;
    if (!WIFEXITED(status) || WEXITSTATUS(status)) goto finish;
    puts("own_child_reaped=PASS");
    result=0;
finish:
    if (child>0) {
        /* Only our own unreaped child; no historic/name/group signaling. */
        kill(child,SIGTERM);
        do { ended=waitpid(child,&status,0); } while (ended<0 && errno==EINTR);
        if (ended!=child) result=1;
    }
    if (event[0]>=0) close(event[0]);
    if (event[1]>=0) close(event[1]);
    if (broken[0]>=0) close(broken[0]);
    if (broken[1]>=0) close(broken[1]);
    puts(result ? "PROBE=FAIL" : "PROBE=PASS native_capture_qualified=no");
    return result;
}
