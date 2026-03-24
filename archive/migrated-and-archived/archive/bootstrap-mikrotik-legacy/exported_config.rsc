# 2026-02-27 17:36:40 by RouterOS 7.21.3
# software id = 2WXR-D9RN
#
# model = S53UG+5HaxD2HaxD
# serial number = HM60B05F2NN
/interface bridge
add admin-mac=D0:EA:11::A3:86 auto-mac=no comment=defconf name=bridge
/interface wifi38
set [ find default-name=wifi1 ] channel.skip-dfs-channels=10min-cac \
    configuration.mode=ap .ssid=Chateau* disabled=no \
    security.authentication-types=wpa2-psk,wpa3-psk .ft=yes .ft-over-ds=yes \
    .passphrase=HX3F66WQYW
set [ find default-name=wifi2 ] channel.skip-dfs-channels=10min-cac \
    configuration.mode=ap .ssid=Chateau disabled=no \
    security.authentication-types=wpa2-psk,wpa3-psk .ft=yes .ft-over-ds=yes \
    .passphrase=HX3F66WQYW
/interface lte
set [ find default-name=lte1 ] allow-roaming=yes band=""
/interface wireguard
add listen-port=51820 mtu=1420 name=wg0 private-key=\
    "iFjypYY48CnGSH6UJtDzlvmp9vZIZjrNdX+iFHc8oUE="
/disk
set usb1 media-interface=bridge media-sharing=yes smb-server-password="" \
    smb-sharing=yes
add media-interface=bridge media-sharing=yes parent=usb1 partition-number=1 \
    partition-offset=16384 partition-size=123048280064 smb-server-password="" \
    smb-sharing=yes type=partition
/interface list
add comment=defconf name=WAN
add comment=defconf name=LAN
/ip pool
add name=default-dhcp ranges=192.168.88.10-192.168.88.254
/ip dhcp-server
add address-pool=default-dhcp interface=bridge name=defconf
/queue type
add fq-codel-ecn=no kind=fq-codel name=fq-codel-ethernet-default
/queue interface
set ether1 queue=fq-codel-ethernet-default
set ether2 queue=fq-codel-ethernet-default
set ether3 queue=fq-codel-ethernet-default
set ether4 queue=fq-codel-ethernet-default
set ether5 queue=fq-codel-ethernet-default
/user group
add name=terraform policy="read,write,policy,test,sensitive,api,rest-api,!loca\
    l,!telnet,!ssh,!ftp,!reboot,!winbox,!password,!web,!sniff,!romon"
/disk settings
set auto-media-interface=bridge auto-media-sharing=yes auto-smb-sharing=yes
/interface bridge port
add bridge=bridge comment=defconf interface=ether2
add bridge=bridge comment=defconf interface=ether3
add bridge=bridge comment=defconf interface=ether4
add bridge=bridge comment=defconf interface=wifi1
add bridge=bridge comment=defconf interface=wifi2
add bridge=bridge interface=ether5
/ip neighbor discovery-settings
set discover-interface-list=LAN
/interface list member
add comment=defconf interface=bridge list=LAN
add comment="Elisa FI Internet" interface=lte1 list=WAN
add interface=wifi1 list=LAN
add interface=wifi2 list=WAN
add interface=ether1 list=WAN
add interface=wg0 list=LAN
/interface wireguard peers
add allowed-address=10.10.10.2/32 endpoint-address=192.168.88.248 \
    endpoint-port=51820 interface=wg0 name=peer3 persistent-keepalive=25s \
    public-key="bFIBipdFZSlJQp8xj7su2pgVA7kMUOY2MMKjB/SZIHw="
/ip address
add address=192.168.88.1/24 comment=defconf interface=bridge network=\
    192.168.88.0
add address=192.168.88.99 comment="mgmt alias" interface=ether1 network=\
    192.168.88.99
add address=10.10.10.1/24 interface=wg0 network=10.10.10.0
add address=192.168.0.99/24 interface=ether1 network=192.168.0.0
/ip dhcp-server network
add address=192.168.88.0/24 comment=defconf dns-server=192.168.88.1 gateway=\
    192.168.88.1
/ip dns
set allow-remote-requests=yes servers=192.168.0.1,1.1.1.1
/ip dns static
add address=192.168.88.1 comment=defconf name=router.lan type=A
/ip firewall filter
add action=accept chain=input comment="Allow REST API" dst-port=8443 \
    protocol=tcp src-address=192.168.88.0/24
add action=accept chain=input comment=\
    "defconf: accept established,related,untracked" connection-state=\
    established,related,untracked
add action=drop chain=input comment="defconf: drop invalid" connection-state=\
    invalid
add action=accept chain=input comment="defconf: accept ICMP" protocol=icmp
add action=accept chain=input comment=\
    "defconf: accept to local loopback (for CAPsMAN)" dst-address=127.0.0.1
add action=accept chain=input comment="allow WireGuard (UDP 51820)" dst-port=\
    51820 in-interface-list=WAN protocol=udp
add action=accept chain=input comment="allow mgmt via WireGuard" \
    in-interface=wg0
add action=accept chain=input comment="WG ICMP (test)" in-interface=wg0 \
    protocol=icmp
add action=accept chain=input comment="allow WG on ether1" dst-port=51820 \
    in-interface=ether1 protocol=udp
add action=accept chain=input comment="allow WG on lte1" dst-port=51820 \
    in-interface=lte1 protocol=udp
add action=drop chain=input comment="defconf: drop all not coming from LAN" \
    in-interface-list=!LAN
add action=accept chain=forward comment="defconf: accept in ipsec policy" \
    ipsec-policy=in,ipsec
add action=accept chain=forward comment="defconf: accept out ipsec policy" \
    ipsec-policy=out,ipsec
add action=fasttrack-connection chain=forward comment="defconf: fasttrack" \
    connection-state=established,related
add action=accept chain=forward comment=\
    "defconf: accept established,related, untracked" connection-state=\
    established,related,untracked
add action=accept chain=forward comment="LAN -> WG (est/rel)" \
    connection-state=established,related,untracked out-interface=wg0
add action=drop chain=forward comment="defconf: drop invalid" \
    connection-state=invalid
add action=accept chain=forward comment="LAN -> WG" dst-address=10.10.10.0/24 \
    out-interface=wg0 src-address=192.168.88.0/24
add action=accept chain=forward comment="WG -> LAN" dst-address=\
    192.168.88.0/24 in-interface=wg0
add action=drop chain=forward comment=\
    "defconf: drop all from WAN not DSTNATed" connection-nat-state=!dstnat \
    connection-state=new in-interface-list=WAN
add action=accept chain=input comment="WinBox via WG" dst-port=8291 \
    in-interface=wg0 protocol=tcp
/ip firewall nat
add action=masquerade chain=srcnat comment="defconf: masquerade" \
    ipsec-policy=out,none out-interface-list=WAN
add action=masquerade chain=srcnat comment="NAT for WG clients" \
    out-interface-list=WAN src-address=10.10.10.0/24
add action=masquerade chain=srcnat comment="NAT for WG clients" \
    out-interface-list=WAN src-address=10.10.10.0/24
/ip route
add check-gateway=ping comment="WAN primary via Slate" distance=1 \
    dst-address=0.0.0.0/0 gateway=192.168.8.1
add dst-address=0.0.0.0/0 gateway=192.168.0.1
/ip service
set www-ssl certificate=local-cert disabled=no port=8443
/ipv6 firewall address-list
add address=::/128 comment="defconf: unspecified address" list=bad_ipv6
add address=::1/128 comment="defconf: lo" list=bad_ipv6
add address=fec0::/10 comment="defconf: site-local" list=bad_ipv6
add address=::ffff:0.0.0.0/96 comment="defconf: ipv4-mapped" list=bad_ipv6
add address=::/96 comment="defconf: ipv4 compat" list=bad_ipv6
add address=100::/64 comment="defconf: discard only " list=bad_ipv6
add address=2001:db8::/32 comment="defconf: documentation" list=bad_ipv6
add address=2001:10::/28 comment="defconf: ORCHID" list=bad_ipv6
add address=3ffe::/16 comment="defconf: 6bone" list=bad_ipv6
/ipv6 firewall filter
add action=accept chain=input comment=\
    "defconf: accept established,related,untracked" connection-state=\
    established,related,untracked
add action=drop chain=input comment="defconf: drop invalid" connection-state=\
    invalid
add action=accept chain=input comment="defconf: accept ICMPv6" protocol=\
    icmpv6
add action=accept chain=input comment="defconf: accept UDP traceroute" \
    dst-port=33434-33534 protocol=udp
add action=accept chain=input comment=\
    "defconf: accept DHCPv6-Client prefix delegation." dst-port=546 protocol=\
    udp src-address=fe80::/10
add action=accept chain=input comment="defconf: accept IKE" dst-port=500,4500 \
    protocol=udp
add action=accept chain=input comment="defconf: accept ipsec AH" protocol=\
    ipsec-ah
add action=accept chain=input comment="defconf: accept ipsec ESP" protocol=\
    ipsec-esp
add action=accept chain=input comment=\
    "defconf: accept all that matches ipsec policy" ipsec-policy=in,ipsec
add action=drop chain=input comment=\
    "defconf: drop everything else not coming from LAN" in-interface-list=\
    !LAN
add action=fasttrack-connection chain=forward comment="defconf: fasttrack6" \
    connection-state=established,related
add action=accept chain=forward comment=\
    "defconf: accept established,related,untracked" connection-state=\
    established,related,untracked
add action=drop chain=forward comment="defconf: drop invalid" \
    connection-state=invalid
add action=drop chain=forward comment=\
    "defconf: drop packets with bad src ipv6" src-address-list=bad_ipv6
add action=drop chain=forward comment=\
    "defconf: drop packets with bad dst ipv6" dst-address-list=bad_ipv6
add action=drop chain=forward comment="defconf: rfc4890 drop hop-limit=1" \
    hop-limit=equal:1 protocol=icmpv6
add action=accept chain=forward comment="defconf: accept ICMPv6" protocol=\
    icmpv6
add action=accept chain=forward comment="defconf: accept HIP" protocol=139
add action=accept chain=forward comment="defconf: accept IKE" dst-port=\
    500,4500 protocol=udp
add action=accept chain=forward comment="defconf: accept ipsec AH" protocol=\
    ipsec-ah
add action=accept chain=forward comment="defconf: accept ipsec ESP" protocol=\
    ipsec-esp
add action=accept chain=forward comment=\
    "defconf: accept all that matches ipsec policy" ipsec-policy=in,ipsec
add action=drop chain=forward comment=\
    "defconf: drop everything else not coming from LAN" in-interface-list=\
    !LAN
/ipv6 nd
set [ find default=yes ] advertise-dns=yes
/system clock
set time-zone-name=Europe/Helsinki
/system routerboard mode-button
set enabled=yes on-event=dark-mode
/system routerboard wps-button
set enabled=yes on-event=wps-accept
/system script
add comment=defconf dont-require-permissions=no name=dark-mode owner=*sys \
    policy=ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon \
    source="\r\
    \n   :if ([system leds settings get all-leds-off] = \"never\") do={\r\
    \n     /system leds settings set all-leds-off=immediate \r\
    \n   } else={\r\
    \n     /system leds settings set all-leds-off=never \r\
    \n   }\r\
    \n "
add comment=defconf dont-require-permissions=no name=wps-accept owner=*sys \
    policy=ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon \
    source="\r\
    \n   :foreach iface in=[/interface/wifi find where (configuration.mode=\"a\
    p\" && disabled=no)] do={\r\
    \n     /interface/wifi wps-push-button \$iface;}\r\
    \n "
/tool mac-server
set allowed-interface-list=LAN
/tool mac-server mac-winbox
set allowed-interface-list=LAN
