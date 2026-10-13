/* Read-only compatibility probe for OpenSSH's rlimit sandbox.
 * No listener, mount, service action, file write or privilege change.
 * Limits affect only this short-lived probe process, never its parent shell.
 * Run only as a separately reviewed candidate runtime test.
 */
#include <sys/types.h>
#include <sys/time.h>
#include <sys/resource.h>
#include <sys/select.h>
#include <poll.h>
#include <fcntl.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    int fd, select_ok, pselect_ok, poll_ok;
    fd_set fds;
    struct timeval tv = {1, 0};
    struct timespec ts = {1, 0};
    struct pollfd pfd;
    struct rlimit zero = {0, 0};
    (void)argv;
    if (argc != 1) {
        fputs("Probe takes no arguments.\n", stderr);
        return 2;
    }
    fd = open("/dev/null", O_RDONLY);
    if (fd < 0 || fd >= FD_SETSIZE) {
        fputs("Probe dependency unavailable.\n", stderr);
        return 2;
    }
    if (setrlimit(RLIMIT_FSIZE, &zero) ||
        setrlimit(RLIMIT_NPROC, &zero) ||
        setrlimit(RLIMIT_NOFILE, &zero)) {
        close(fd);
        fputs("Probe resource limits refused.\n", stderr);
        return 2;
    }
    FD_ZERO(&fds);
    FD_SET(fd, &fds);
    select_ok = select(fd + 1, &fds, NULL, NULL, &tv) >= 0;
    FD_ZERO(&fds);
    FD_SET(fd, &fds);
    pselect_ok = pselect(fd + 1, &fds, NULL, NULL, &ts, NULL) >= 0;
    pfd.fd = fd;
    pfd.events = POLLIN;
    pfd.revents = 0;
    poll_ok = poll(&pfd, 1, 1) >= 0;
    close(fd);
    printf("{\"schema\":\"nimbus-rlimit-probe/v1\",\"select_with_nofile_zero\":%s,"
           "\"pselect_with_nofile_zero\":%s,\"poll_with_nofile_zero\":%s,"
           "\"scope\":\"process_compatibility_only\"}\n",
           select_ok ? "true" : "false", pselect_ok ? "true" : "false",
           poll_ok ? "true" : "false");
    /* Candidate uses OpenSSHs select/pselect fallback, not libc poll. */
    return select_ok && pselect_ok ? 0 : 1;
}
