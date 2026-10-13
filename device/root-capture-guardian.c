/* Inactive disconnect-owner candidate. Unpinned builds REFUSE execution.
 * Pinned builds fix native entry/stage/input hashes; no live launcher approved.
 * The owner detaches from the SSH session, bounds relay/log memory, and never
 * declares restoration. It cannot recover from SIGKILL, power loss or stuck IO.
 */
#define _POSIX_C_SOURCE 200809L
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/select.h>
#include <sys/wait.h>
#include <poll.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#if defined(NIMBUS_GUARDIAN_FIXTURE) || defined(NIMBUS_GUARDIAN_PINNED)
#ifdef NIMBUS_GUARDIAN_PINNED
#include "guardian-pins.h"
#include "root-capture-sha256.h"
#endif
#define BUFFER 65536
#define LOG_LIMIT 131072
#ifndef NIMBUS_GUARDIAN_DEADLINE_SECONDS
#define NIMBUS_GUARDIAN_DEADLINE_SECONDS 300
#endif
static volatile sig_atomic_t cancelled;
static unsigned char outgoing[BUFFER], incoming[256], scratch[BUFFER];
static void cancel(int signum) { (void)signum; cancelled = 1; }

static int nonblock(int fd)
{
    int flags = fcntl(fd, F_GETFL);
    return flags < 0 ? -1 : fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}

static int save(int fd, const void *data, size_t bytes)
{
    const unsigned char *p = data;
    while (bytes) {
        ssize_t n = write(fd, p, bytes);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return -1;
        p += n; bytes -= (size_t)n;
    }
    return 0;
}

static int private_file(const char *name)
{
    return open(name, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
}

static int inherited_fds_ok(void)
{
    DIR *directory = opendir("/proc/self/fd");
    struct dirent *entry;
    int okay = 1, fd;
    struct stat st;
    if (!directory) return 0;
    for (fd = 0; fd < 3; fd++)
        if (fstat(fd, &st) || !(S_ISFIFO(st.st_mode) || S_ISSOCK(st.st_mode))) okay = 0;
    errno = 0;
    while ((entry = readdir(directory))) {
        char *end;
        long number;
        if (entry->d_name[0] == '.') continue;
        number = strtol(entry->d_name, &end, 10);
        if (*end || number < 0 || (number > 2 && number != dirfd(directory))) okay = 0;
    }
    if (errno) okay = 0;
    closedir(directory);
    return okay;
}

#ifdef NIMBUS_GUARDIAN_PINNED
static int pinned_file(const char *name, const char *expected, mode_t mode)
{
    struct stat st;
    char digest[65];
    int fd=open(name,O_RDONLY|O_NOFOLLOW|O_NONBLOCK), okay;
    if (fd<0) return 0;
    okay=!fstat(fd,&st) && S_ISREG(st.st_mode) && st.st_uid==geteuid() &&
         (st.st_mode&07777)==mode && st.st_size>0 && st.st_size<=1048576 &&
         !sha_file(fd,digest) && !strcmp(digest,expected);
    close(fd);
    return okay;
}
static int staged_inputs_ok(const char *token)
{
    struct stat st;
    char marker[65];
    int fd, okay;
    static const char *used[]={"GUARDIAN-CLAIM","GUARDIAN-RESULT","GUARDIAN-INVALID","GUARDIAN-STDERR.log","CHILD-DRAIN","RESULT"};
    size_t i;
    for (i=0;i<sizeof(used)/sizeof(used[0]);i++)
        if (!lstat(used[i],&st) || errno!=ENOENT) return 0;
    if (!pinned_file("worker.sh",NIMBUS_WORKER_SHA,0600) ||
        !pinned_file("identity.sh",NIMBUS_IDENTITY_SHA,0600) ||
        !pinned_file("streamer",NIMBUS_STREAM_SHA,0700) ||
        !pinned_file("SHA256SUMS",NIMBUS_SUMS_SHA,0600)) return 0;
    fd=open("started",O_RDONLY|O_NOFOLLOW|O_NONBLOCK);
    if (fd<0) return 0;
    okay=!fstat(fd,&st) && S_ISREG(st.st_mode) && st.st_uid==geteuid() &&
         (st.st_mode&07777)==0600 && st.st_size==65 && read(fd,marker,65)==65 &&
         !memcmp(marker,token,64) && marker[64]=='\n';
    close(fd);
    if (!okay) return 0;
    fd=open("worker.log",O_RDONLY|O_NOFOLLOW|O_NONBLOCK);
    if (fd<0) return 0;
    okay=!fstat(fd,&st) && S_ISREG(st.st_mode) && st.st_uid==geteuid() &&
         (st.st_mode&07777)==0600 && st.st_size==0;
    close(fd);
    return okay;
}
#endif

static int run_owner(const char *token, int logfd)
{
    int control[2], output[2], errors[2], status = 0, reaped = 0;
    int failed = 0, signalled = 0, invalid_recorded = 0, output_open = 1, errors_open = 1;
    size_t queued = 0, ack_queued = 0, ack_total = 0, logged = 0;
    pid_t worker;
    struct sigaction action;
    char evidence[256];
    int evidence_fd, result;
    struct timespec began, now;
    if (setsid() < 0) return 1;
    memset(&action, 0, sizeof(action));
    action.sa_handler = cancel;
    sigemptyset(&action.sa_mask);
    if (sigprocmask(SIG_SETMASK,&action.sa_mask,NULL) || sigaction(SIGHUP, &action, NULL) || sigaction(SIGINT, &action, NULL) ||
        sigaction(SIGTERM, &action, NULL) || signal(SIGPIPE, SIG_IGN) == SIG_ERR) return 1;
    if (pipe(control) || pipe(output) || pipe(errors)) return 1;
    if (control[1] >= FD_SETSIZE || output[0] >= FD_SETSIZE || errors[0] >= FD_SETSIZE) return 1;
    if (clock_gettime(CLOCK_MONOTONIC, &began)) return 1;
    worker = fork();
    if (worker < 0) return 1;
    if (!worker) {
        int fd;
        if (dup2(control[0], 0) < 0 || dup2(output[1], 1) < 0 || dup2(errors[1], 2) < 0) _exit(127);
        /* All supervisor-owned descriptors are below FD_SETSIZE. Fixture caller
         * must use close_fds; native inherited-FD census is still a live gate. */
        for (fd = 3; fd < FD_SETSIZE; fd++) close(fd);
        signal(SIGHUP, SIG_DFL); signal(SIGINT, SIG_DFL); signal(SIGTERM, SIG_DFL);
        signal(SIGPIPE, SIG_DFL);
        execl("/bin/sh", "sh", "./worker.sh", "--worker", token, (char *)NULL);
        _exit(127);
    }
    close(control[0]); close(output[1]); close(errors[1]);
    if (nonblock(0) || nonblock(1) || nonblock(control[1]) || nonblock(output[0]) || nonblock(errors[0])) failed = 1;
    while (!reaped || output_open || errors_open || queued) {
        fd_set reads, writes;
        struct timeval delay = {0, 100000};
        struct pollfd peer = {1, 0, 0};
        int ready, maximum = errors[0] > output[0] ? errors[0] : output[0];
        if (!reaped) {
            pid_t ended = waitpid(worker, &status, WNOHANG);
            if (ended == worker) {
                reaped = 1;
                if (!WIFEXITED(status) || WEXITSTATUS(status)) failed = 1;
            }
            else if (ended < 0 && errno != EINTR) { failed = 1; break; }
        }
        if (cancelled) failed = 1;
        if (clock_gettime(CLOCK_MONOTONIC, &now) ||
            now.tv_sec - began.tv_sec > NIMBUS_GUARDIAN_DEADLINE_SECONDS ||
            (now.tv_sec - began.tv_sec == NIMBUS_GUARDIAN_DEADLINE_SECONDS && now.tv_nsec >= began.tv_nsec)) failed = 1;
        if (!failed && (poll(&peer, 1, 0) < 0 || (peer.revents & (POLLERR | POLLHUP | POLLNVAL)))) failed = 1;
        if (failed) {
            queued = 0; ack_queued = 0;
            if (!invalid_recorded) {
                int invalid_fd = private_file("GUARDIAN-INVALID");
                invalid_recorded = 1;
                if (invalid_fd >= 0) {
                    /* Attempt remains invalid even if private recording fails. */
                    (void)save(invalid_fd, token, 64);
                    (void)fsync(invalid_fd);
                    close(invalid_fd);
                }
            }
            if (control[1] >= 0) { close(control[1]); control[1] = -1; }
            /* Only the unreaped direct child: never historic PID/name/group.
             * TERM is a cooperative request, not proof of descendant shutdown. */
            if (!reaped && !signalled) { kill(worker, SIGTERM); signalled = 1; }
        }
        FD_ZERO(&reads); FD_ZERO(&writes);
        if (!failed && !reaped && ack_queued == 0) FD_SET(0, &reads);
        if (output_open && (failed || queued == 0)) FD_SET(output[0], &reads);
        if (errors_open) FD_SET(errors[0], &reads);
        if (!failed && queued) FD_SET(1, &writes);
        if (!failed && control[1] >= 0 && ack_queued) {
            FD_SET(control[1], &writes);
            if (control[1] > maximum) maximum = control[1];
        }
        ready = select(maximum + 1, &reads, &writes, NULL, &delay);
        if (ready < 0) { if (errno != EINTR) failed = 1; continue; }
        if (FD_ISSET(0, &reads)) {
            /* Read one extra byte to detect any excess without unbounded queues. */
            unsigned char ack[257];
            ssize_t n = read(0, ack, sizeof(ack));
            if (n > 0 && ack_total + (size_t)n <= sizeof(incoming)) {
                memcpy(incoming, ack, (size_t)n); ack_queued = (size_t)n; ack_total += (size_t)n;
            } else if (n == 0 || n > 0 || (errno != EAGAIN && errno != EINTR)) failed = 1;
        }
        if (control[1] >= 0 && FD_ISSET(control[1], &writes)) {
            ssize_t n = write(control[1], incoming, ack_queued);
            if (n > 0) { ack_queued -= (size_t)n; memmove(incoming, incoming + n, ack_queued); }
            else if (n == 0 || (errno != EAGAIN && errno != EINTR)) failed = 1;
        }
        if (FD_ISSET(output[0], &reads)) {
            ssize_t n = read(output[0], failed ? scratch : outgoing, BUFFER);
            if (n > 0 && !failed) queued = (size_t)n;
            else if (n == 0) { output_open = 0; close(output[0]); }
            else if (n < 0 && errno != EAGAIN && errno != EINTR) { failed = 1; output_open = 0; close(output[0]); }
        }
        if (FD_ISSET(errors[0], &reads)) {
            ssize_t n = read(errors[0], scratch, BUFFER);
            if (n > 0) {
                size_t available = LOG_LIMIT - logged, bytes = (size_t)n;
                if (bytes > available) { bytes = available; failed = 1; }
                if (bytes && save(logfd, scratch, bytes)) failed = 1;
                logged += bytes;
            } else if (n == 0) { errors_open = 0; close(errors[0]); }
            else if (errno != EAGAIN && errno != EINTR) { failed = 1; errors_open = 0; close(errors[0]); }
        }
        if (FD_ISSET(1, &writes) && !failed) {
            ssize_t n = write(1, outgoing, queued);
            if (n > 0) { queued -= (size_t)n; memmove(outgoing, outgoing + n, queued); }
            else if (n == 0 || (errno != EAGAIN && errno != EINTR)) failed = 1;
        }
    }
    if (control[1] >= 0) close(control[1]);
    if (!reaped) {
        pid_t ended;
        do { ended = waitpid(worker, &status, 0); } while (ended < 0 && errno == EINTR);
        if (ended == worker) reaped = 1;
    }
    if (cancelled || !reaped || !WIFEXITED(status) || WEXITSTATUS(status)) failed = 1;
    if (fsync(logfd)) failed = 1;
    result = failed ? 1 : 0;
    snprintf(evidence, sizeof(evidence), "%s invalidated=%s worker_exited=%s worker_status=%d restoration_certified=no\n",
             token, failed ? "yes" : "no", reaped ? "yes" : "no", status);
    evidence_fd = private_file("GUARDIAN-RESULT");
    if (evidence_fd < 0) return 1;
    if (save(evidence_fd, evidence, strlen(evidence)) || fsync(evidence_fd)) result = 1;
    close(evidence_fd);
    /* Persistent evidence is tmpfs fixture evidence, not power-loss durability. */
    return result;
}

int main(int argc, char **argv)
{
    struct stat st;
    int claim, logfd, status;
    size_t i;
    pid_t owner, ended;
    struct sigaction child_action;
    const char *stage;
    int stagefd, check_mode=0;
#ifdef NIMBUS_GUARDIAN_FIXTURE
#ifdef NIMBUS_GUARDIAN_PINNED
    if (argc!=4 || (strcmp(argv[1],"--fixture") && strcmp(argv[1],"--fixture-check")) || argv[3][0]!='/' || strlen(argv[2])!=64) return 2;
    check_mode=!strcmp(argv[1],"--fixture-check");
#else
    if (argc != 4 || strcmp(argv[1], "--fixture") || argv[3][0] != '/' || strlen(argv[2]) != 64) return 2;
#endif
    stage=argv[3];
#else
    const char *connection=getenv("SSH_CONNECTION"), *port;
    if (argc!=3 || (strcmp(argv[1],"--check") && strcmp(argv[1],"--supervise")) || strlen(argv[2])!=64) return 2;
    port=connection ? strrchr(connection,' ') : NULL;
    if (geteuid()!=0 || !port || strcmp(port+1,"2225")) return 1;
    check_mode=!strcmp(argv[1],"--check");
    stage="/tmp/nimbus-root-capture-v1";
#endif
    for (i = 0; i < 64; i++)
        if (!((argv[2][i] >= 'a' && argv[2][i] <= 'f') || (argv[2][i] >= '0' && argv[2][i] <= '9'))) return 2;
    if (!inherited_fds_ok()) return 1;
    stagefd=open(stage,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
    if (stagefd<0) return 1;
    if (fstat(stagefd,&st) || !S_ISDIR(st.st_mode) || st.st_uid!=geteuid() || (st.st_mode&07777)!=0700 || fchdir(stagefd)) { close(stagefd);return 1; }
    close(stagefd);
    if (lstat("worker.sh", &st) || !S_ISREG(st.st_mode) || st.st_uid != getuid() ||
        (st.st_mode & 0777) != 0600 || st.st_size > 65536) return 1;
#ifdef NIMBUS_GUARDIAN_PINNED
    if (!staged_inputs_ok(argv[2])) return 1;
#endif
    if (check_mode) return 0; /* No claim/log/worker/action. */
    memset(&child_action,0,sizeof(child_action));
    child_action.sa_handler=SIG_DFL;
    sigemptyset(&child_action.sa_mask);
    if (sigaction(SIGCHLD,&child_action,NULL)) return 1; /* Never inherit automatic child reaping. */
    claim = private_file("GUARDIAN-CLAIM");
    if (claim < 0) return 1;
    if (save(claim, argv[2], 64) || fsync(claim)) { close(claim); return 1; }
    close(claim);
    logfd = private_file("GUARDIAN-STDERR.log");
    if (logfd < 0) return 1;
    owner = fork();
    if (owner < 0) { close(logfd); return 1; }
    if (!owner) _exit(run_owner(argv[2], logfd));
    close(logfd); close(0); close(1); close(2);
    /* This SSH-side waiter owns no data/control/log FD. Its death cannot kill
     * the setsid owner. In normal operation it propagates the owner's status. */
    do { ended = waitpid(owner, &status, 0); } while (ended < 0 && errno == EINTR);
    return ended == owner && WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}
#else
int main(void) { return 2; } /* No native action entry until reviewed staging/identity integration. */
#endif
