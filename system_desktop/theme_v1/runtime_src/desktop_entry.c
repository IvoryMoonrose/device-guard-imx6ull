/* Preserve the vendor executable's directory and argv[0] for existing tools. */
#define _GNU_SOURCE
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#define ROOT "/opt/device_guard/system_theme"
int main(int argc,char **argv){
    /* Boot has HOME=/ while SSH has HOME=/home/root. Keep QRC caches isolated
       from both vendor cache trees, including caches with fixed RCC timestamps. */
    mkdir(ROOT "/cache",0755);mkdir(ROOT "/cache/v2",0755);
    setenv("XDG_CACHE_HOME",ROOT "/cache/v2",1);
    if(!getenv("QT_QPA_FONTDIR"))setenv("QT_QPA_FONTDIR","/usr/share/fonts/ttf",1);
    if(!getenv("QT_QUICK_BACKEND"))setenv("QT_QUICK_BACKEND","software",1);
    if(!getenv("QT_QPA_PLATFORM"))setenv("QT_QPA_PLATFORM","linuxfb:tty=/dev/fb0",1);
    if(!getenv("QT_QPA_FB_TSLIB"))setenv("QT_QPA_FB_TSLIB","1",1);
    (void)argc;mkdir(ROOT "/runtime",0755);int alive=0;FILE *f=fopen(ROOT "/runtime/nav.pid","r");
    if(f){int pid;if(fscanf(f,"%d",&pid)==1&&pid>1&&!kill(pid,0)){char path[128],cmd[512];snprintf(path,sizeof(path),"/proc/%d/cmdline",pid);int fd=open(path,O_RDONLY);if(fd>=0){ssize_t n=read(fd,cmd,sizeof(cmd)-1);close(fd);if(n>0){cmd[n]=0;alive=!strcmp(cmd,ROOT "/bin/navd");}}}fclose(f);}
    if(!alive){pid_t pid=fork();if(pid==0){setsid();int fd=open(ROOT "/runtime/nav.log",O_CREAT|O_WRONLY|O_APPEND,0644);if(fd>=0){dup2(fd,1);dup2(fd,2);close(fd);}execl(ROOT "/bin/navd",ROOT "/bin/navd",(char*)0);_exit(127);}}
    argv[0]="/opt/ui/systemui";execv("/opt/ui/systemui.core",argv);perror("systemui.core");return 1;
}
