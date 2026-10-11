# POSIX awk: serialize read-only local telemetry and validated feature metadata.
function quote(value,    result,i,c) {
    result="\""
    for(i=1;i<=length(value);i++) {
        c=substr(value,i,1)
        if(c=="\\") result=result "\\\\"
        else if(c=="\"") result=result "\\\""
        else if(c in control) result=result sprintf("\\u%04x",control[c])
        else result=result c
    }
    return result "\""
}
function hex(value,    result,i,c) {
    result=0; value=toupper(value)
    for(i=1;i<=length(value);i++) {c=index("0123456789ABCDEF",substr(value,i,1))-1; if(c<0)return 0; result=result*16+c}
    return result
}
function address(value) {return hex(substr(value,7,2)) "." hex(substr(value,5,2)) "." hex(substr(value,3,2)) "." hex(substr(value,1,2))}
BEGIN {for(i=1;i<32;i++)control[sprintf("%c",i)]=i; FS="[ \t]+"; uptime=0; total=0; reclaimable=0; gateways=0; networks=0; interfaces=0; features=0; files=0}
FILENAME==uptime_file {uptime=$1+0; next}
FILENAME==memory_file {
    if($1=="MemTotal:")total=$2+0
    if($1=="MemFree:"||$1=="Buffers:"||$1=="Cached:")reclaimable+=$2
    next
}
FILENAME==routes_file {
    if($1=="Iface"||NF<8)next
    if($2=="00000000"&&$3!="00000000") {gateway=address($3); uplink=$1; gateways++}
    else if($1!="lo"&&$2!="00000000") {networks++; net_iface[networks]=$1; net_ip[networks]=address($2); net_mask[networks]=address($8)}
    next
}
FILENAME==interfaces_file {
    separator=index($0,":"); if(!separator)next
    name=substr($0,1,separator-1); gsub(/^[ \t]+|[ \t]+$/,"",name)
    rest=substr($0,separator+1); gsub(/^[ \t]+|[ \t]+$/,"",rest); count=split(rest,counters,/[ \t]+/)
    if(count<12||counters[1]!~/^[0-9]+$/||name!~/^[A-Za-z0-9_.-]+$/)next
    interfaces++; if_name[interfaces]=name; rx[interfaces]=counters[1]+0; tx[interfaces]=counters[9]+0
    errors[interfaces]=counters[3]+counters[11]; drops[interfaces]=counters[4]+counters[12]
    next
}
FILENAME==features_file {
    split($0,fields,"\t"); features++; feature_name[features]=fields[1]; feature_on[features]=(fields[2]=="on"); feature_available[features]=(fields[3]=="yes"); feature_reason[features]=fields[4]; next
}
FILENAME==vault_file {
    split($0,fields,"\t"); if(fields[2]!~/^[0-9]+$/)next
    files++; file_name[files]=fields[1]; file_size[files]=fields[2]+0; next
}
FILENAME==tcp_file {
    line=$0; gsub(/^[ \t]+|[ \t]+$/,"",line); split(line,tcp_fields,/[ \t]+/)
    if(tcp_fields[4]!="0A")next
    split(tcp_fields[2],parts,":"); port=hex(parts[2]); listening[port]=1; next
}
END {
    printf "{\"schema\":\"nimbus-dashboard/v1\",\"scope\":\"device\",\"generated_at\":%.0f,\"publisher\":%s,\"install_path\":%s,\"hostname\":%s,\"firmware\":\"3.04 (previously verified)\",", generated_at,quote(publisher),quote(install_path),quote(hostname)
    printf "\"uptime_seconds\":%.2f,\"memory\":{\"total_bytes\":%.0f,\"reclaimable_estimate_bytes\":%.0f},",uptime,total*1024,reclaimable*1024
    printf "\"storage\":{\"path\":%s,\"total\":%.0f,\"used\":%.0f,\"free\":%.0f},",quote(install_path),disk_total*1024,disk_used*1024,disk_free*1024
    printf "\"battery\":{\"capacity\":%s,\"status\":%s},",(battery_capacity~/^[0-9]+$/&&battery_capacity+0<=100)?sprintf("%.0f",battery_capacity+0):"null",quote(battery_status)
    printf "\"network\":{\"gateway\":%s,\"uplink\":%s,\"internet_verified\":false,\"subnets\":[",gateways?quote(gateway):"null",gateways?quote(uplink):"null"
    for(i=1;i<=networks;i++)printf "%s{\"interface\":%s,\"address\":%s,\"mask\":%s}",(i>1?",":""),quote(net_iface[i]),quote(net_ip[i]),quote(net_mask[i])
    printf "],\"interfaces\":["
    for(i=1;i<=interfaces;i++)printf "%s{\"name\":%s,\"rx_bytes\":%.0f,\"tx_bytes\":%.0f,\"errors\":%.0f,\"drops\":%.0f}",(i>1?",":""),quote(if_name[i]),rx[i],tx[i],errors[i],drops[i]
    printf "]},\"services\":{\"source\":\"kernel TCP listeners (not reachability or authentication)\",\"ftp\":%s,\"telnet\":%s,\"http\":%s,\"ssh\":%s,\"https\":%s},",listening[21]?"true":"false",listening[23]?"true":"false",listening[80]?"true":"false",listening[22]?"true":"false",listening[443]?"true":"false"
    printf "\"features\":["
    for(i=1;i<=features;i++)printf "%s{\"id\":%s,\"enabled\":%s,\"available\":%s,\"reason\":%s}",(i>1?",":""),quote(feature_name[i]),feature_on[i]?"true":"false",feature_available[i]?"true":"false",quote(feature_reason[i])
    printf "],\"vault\":["
    for(i=1;i<=files;i++)printf "%s{\"name\":%s,\"bytes\":%.0f}",(i>1?",":""),quote(file_name[i]),file_size[i]
    printf "],\"monitor_mode\":\"excluded\"}\n"
}
