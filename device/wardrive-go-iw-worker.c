/* Inactive fixed READ-ONLY iw worker using the synthetic supervisor core.
 * Not a scan worker or complete sandbox. Production refuses root/shared groups.
 * RLIMIT_NPROC prevents ordinary non-root fork, not a malicious exec escalation.
 * Requires separately provisioned dedicated identity/native qualification.
 */
#define _POSIX_C_SOURCE 200809L
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/resource.h>
#include <sys/xattr.h>
#include <sys/prctl.h>
#include <fcntl.h>
#include <dirent.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "root-capture-sha256.h"

#ifndef GO_IW_FIXTURE
#define GO_IW_PATH "/usr/sbin/iw"
#define GO_IW_HASH "468f4271f5af9eaa5380f30b9717a58462baec4596e87461ff23859dfe44321e"
#define GO_IW_BYTES 160508
#endif
static int executable=-1;

static int prepare_iw(void)
{
    struct stat before,after;
    char hash[65];
    uid_t owner=0;gid_t group=0;
    if (geteuid()==0 || getuid()!=geteuid() || getgid()!=getegid()) return -1;
#ifndef GO_IW_FIXTURE
    if (getegid()==0 || getgroups(0,NULL)!=0) return -1;
#else
    owner=geteuid();group=getegid();
#endif
    executable=open(GO_IW_PATH,O_RDONLY|O_NOFOLLOW);
    if (executable<3 || fstat(executable,&before) || !S_ISREG(before.st_mode) ||
        before.st_uid!=owner || before.st_gid!=group || before.st_nlink!=1 ||
        (before.st_mode & 07777)!=0755 || before.st_size!=GO_IW_BYTES) goto refused;
    errno=0;
    if (fgetxattr(executable,"security.capability",NULL,0)>=0 || errno!=ENODATA) goto refused;
    if (sha_file(executable,hash) || strcmp(hash,GO_IW_HASH) || fstat(executable,&after) ||
        before.st_dev!=after.st_dev || before.st_ino!=after.st_ino ||
        before.st_size!=after.st_size || before.st_mtime!=after.st_mtime ||
        before.st_ctime!=after.st_ctime) goto refused;
    return 0;
refused:
    if (executable>=0) close(executable);
    executable=-1;return -1;
}

static void run_iw(const char *mode)
{
    struct rlimit no_processes={0,0},no_core={0,0},no_files={0,0};
    DIR *directory;
    struct dirent *entry;
    char *arguments[]={"iw",(char *)mode,NULL};
    char *environment[]={"LC_ALL=C","PATH=/nonexistent",NULL};
    /* Existing inherited effective capabilities would bypass NPROC. Require
     * an unprivileged invocation, and refuse platforms without readable caps. */
    FILE *caps=fopen("/proc/self/status","r");
    char line[256];int checked=0;
    if (!caps) _exit(18);
    while (fgets(line,sizeof(line),caps)) {
        unsigned long long value;
        if (!strncmp(line,"CapInh:",7) || !strncmp(line,"CapPrm:",7) || !strncmp(line,"CapEff:",7)) {
            if (sscanf(line+7,"%llx",&value)!=1 || value) {fclose(caps);_exit(19);}
            checked++;
        }
    }
    fclose(caps);
    if (checked!=3 || setrlimit(RLIMIT_NPROC,&no_processes) ||
        setrlimit(RLIMIT_CORE,&no_core) || setrlimit(RLIMIT_FSIZE,&no_files)) _exit(20);
    /* No inherited keys/control/private files reach the external executable.
     * Keep only the held executable and bounded stdout pipe; no stderr leaks. */
    directory=opendir("/proc/self/fd");if (!directory) _exit(21);
    errno=0;
    while ((entry=readdir(directory))) {
        char *end;long fd;
        if (entry->d_name[0]=='.') continue;
        errno=0;fd=strtol(entry->d_name,&end,10);
        if (errno || *end || fd<0 || fd>INT_MAX) {closedir(directory);_exit(22);}
        if (fd>=3 && fd!=executable && fd!=dirfd(directory)) close((int)fd);
        errno=0;
    }
    if (errno) {closedir(directory);_exit(23);}
    closedir(directory);
    fexecve(executable,arguments,environment);
#ifdef GO_WORKER_DIAGNOSTICS
    _exit(32+errno);
#endif
    _exit(8);
}

#define GO_WORKER_RUN(mode) run_iw(mode)
#define GO_WORKER_PREPARE() prepare_iw()
#define GO_ACTION "--query"
#define GO_CONTROL_ACTION "--query-controlled"
#define GO_VALID_MODE(mode) (!strcmp(mode,"list") || !strcmp(mode,"dev"))
#include "wardrive-go-supervisor.c"
