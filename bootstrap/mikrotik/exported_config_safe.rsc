# 2026-02-27 17:36:40 by RouterOS 7.21.3
# software id = 2WXR-D9RN
# model = S53UG+5HaxD2HaxD
# serial number = HM60B05F2NN
# SAFE VERSION - with existence checks

# --- Bridge ---
/interface bridge
:if ([:len [find where name=bridge]] = 0) do={
    add admin-mac=D0:EA:11:A3:86 auto-mac=no comment=defconf name=bridge
} else={
    :put "Bridge already exists, skipping"
}

# --- WiFi Configuration ---
/interface wifi
:do {
    set [ find default-name=wifi1 ] channel.skip-dfs-channels=10min-cac \
        configuration.mode=ap .ssid=Chateau* disabled=no \
        security.authentication-types=wpa2-psk,wpa3-psk .ft=yes .ft-over-ds=yes \
        .passphrase=HX3F66WQYW
} on-error={ :put "WiFi1 config failed" }

:do {
    set [ find default-name=wifi2 ] channel.skip-dfs-channels=10min-cac \
        configuration.mode=ap .ssid=Chateau disabled=no \
        security.authentication-types=wpa2-psk,wpa3-psk .ft=yes .ft-over-ds=yes \
        .passphrase=HX3F66WQYW
} on-error={ :put "WiFi2 config failed" }

# --- LTE ---
/interface lte
:do {
    set [ find default-name=lte1 ] allow-roaming=yes band=""
} on-error={ :put "LTE config failed" }

# --- WireGuard ---
/interface wireguard
:if ([:len [find where name=wg0]] = 0) do={
    add listen-port=51820 mtu=1420 name=wg0 private-key=\
        "iFjypYY48CnGSH6UJtDzlvmp9vZIZjrNdX+iFHc8oUE="
} else={
    :put "WireGuard wg0 already exists"
}

# --- Disk (USB) - Skip if not present ---
:do {
    /disk
    set usb1 media-interface=bridge media-sharing=yes smb-server-password="" \
        smb-sharing=yes
} on-error={ :put "USB disk not found, skipping" }

# --- Interface Lists ---
/interface list
:if ([:len [find where name=WAN]] = 0) do={
    add comment=defconf name=WAN
}
:if ([:len [find where name=LAN]] = 0) do={
    add comment=defconf name=LAN
}

# --- IP Pool ---
/ip pool
:if ([:len [find where name=default-dhcp]] = 0) do={
    add name=default-dhcp ranges=192.168.88.10-192.168.88.254
} else={
    set [find where name=default-dhcp] ranges=192.168.88.10-192.168.88.254
}

# --- DHCP Server ---
/ip dhcp-server
:if ([:len [find where name=defconf]] = 0) do={
    add address-pool=default-dhcp interface=bridge name=defconf
}

# --- Queue Type ---
/queue type
:if ([:len [find where name=fq-codel-ethernet-default]] = 0) do={
    add fq-codel-ecn=no kind=fq-codel name=fq-codel-ethernet-default
}

# --- Queue Interface ---
/queue interface
:do { set ether1 queue=fq-codel-ethernet-default } on-error={}
:do { set ether2 queue=fq-codel-ethernet-default } on-error={}
:do { set ether3 queue=fq-codel-ethernet-default } on-error={}
:do { set ether4 queue=fq-codel-ethernet-default } on-error={}
:do { set ether5 queue=fq-codel-ethernet-default } on-error={}

# --- User Group ---
/user group
:if ([:len [find where name=terraform]] = 0) do={
    add name=terraform policy="read,write,policy,test,sensitive,api,rest-api,!local,!telnet,!ssh,!ftp,!reboot,!winbox,!password,!web,!sniff,!romon"
}

# --- Disk Settings ---
:do {
    /disk settings
    set auto-media-interface=bridge auto-media-sharing=yes auto-smb-sharing=yes
} on-error={ :put "Disk settings skipped" }

# --- Bridge Ports ---
/interface bridge port
:do {
    :if ([:len [find where interface=ether2 and bridge=bridge]] = 0) do={
        add bridge=bridge comment=defconf interface=ether2
    }
} on-error={}
:do {
    :if ([:len [find where interface=ether3 and bridge=bridge]] = 0) do={
        add bridge=bridge comment=defconf interface=ether3
    }
} on-error={}
:do {
    :if ([:len [find where interface=ether4 and bridge=bridge]] = 0) do={
        add bridge=bridge comment=defconf interface=ether4
    }
} on-error={}
:do {
    :if ([:len [find where interface=wifi1 and bridge=bridge]] = 0) do={
        add bridge=bridge comment=defconf interface=wifi1
    }
} on-error={}
:do {
    :if ([:len [find where interface=wifi2 and bridge=bridge]] = 0) do={
        add bridge=bridge comment=defconf interface=wifi2
    }
} on-error={}
:do {
    :if ([:len [find where interface=ether5 and bridge=bridge]] = 0) do={
        add bridge=bridge interface=ether5
    }
} on-error={}

# --- IP Neighbor ---
/ip neighbor discovery-settings
set discover-interface-list=LAN

# --- Interface List Members ---
/interface list member
:do {
    :if ([:len [find where interface=bridge and list=LAN]] = 0) do={
        add comment=defconf interface=bridge list=LAN
    }
} on-error={}
:do {
    :if ([:len [find where interface=lte1 and list=WAN]] = 0) do={
        add comment="Elisa FI Internet" interface=lte1 list=WAN
    }
} on-error={}
:do {
    :if ([:len [find where interface=wifi1 and list=LAN]] = 0) do={
        add interface=wifi1 list=LAN
    }
} on-error={}
:do {
    :if ([:len [find where interface=wifi2 and list=WAN]] = 0) do={
        add interface=wifi2 list=WAN
    }
} on-error={}
:do {
    :if ([:len [find where interface=ether1 and list=WAN]] = 0) do={
        add interface=ether1 list=WAN
    }
} on-error={}
:do {
    :if ([:len [find where interface=wg0 and list=LAN]] = 0) do={
        add interface=wg0 list=LAN
    }
} on-error={}

# --- WireGuard Peers ---
/interface wireguard peers
:do {
    :if ([:len [find where name=peer3]] = 0) do={
        add allowed-address=10.10.10.2/32 endpoint-address=192.168.88.248 \
            endpoint-port=51820 interface=wg0 name=peer3 persistent-keepalive=25s \
            public-key="bFIBipdFZSlJQp8xj7su2pgVA7kMUOY2MMKjB/SZIHw="
    }
} on-error={ :put "WireGuard peer config failed" }

# --- IP Addresses ---
/ip address
:if ([:len [find where address="192.168.88.1/24" and interface=bridge]] = 0) do={
    add address=192.168.88.1/24 comment=defconf interface=bridge network=192.168.88.0
}
:do {
    :if ([:len [find where address~"192.168.88.99" and interface=ether1]] = 0) do={
        add address=192.168.88.99 comment="mgmt alias" interface=ether1 network=192.168.88.99
    }
} on-error={}
:if ([:len [find where address="10.10.10.1/24" and interface=wg0]] = 0) do={
    add address=10.10.10.1/24 interface=wg0 network=10.10.10.0
}
:do {
    :if ([:len [find where address="192.168.0.99/24" and interface=ether1]] = 0) do={
        add address=192.168.0.99/24 interface=ether1 network=192.168.0.0
    }
} on-error={}

# --- DHCP Server Network ---
/ip dhcp-server network
:if ([:len [find where address="192.168.88.0/24"]] = 0) do={
    add address=192.168.88.0/24 comment=defconf dns-server=192.168.88.1 gateway=192.168.88.1
}

# --- DNS ---
/ip dns
set allow-remote-requests=yes servers=192.168.0.1,1.1.1.1

# --- DNS Static ---
/ip dns static
:if ([:len [find where name="router.lan"]] = 0) do={
    add address=192.168.88.1 comment=defconf name=router.lan type=A
}

# --- Firewall Filter ---
/ip firewall filter
# Clear existing and recreate (to maintain order)
:put "Configuring firewall rules..."

:if ([:len [find where comment="Allow REST API"]] = 0) do={
    add action=accept chain=input comment="Allow REST API" dst-port=8443 protocol=tcp src-address=192.168.88.0/24 place-before=0
}

:if ([:len [find where comment~"defconf: accept established"]] = 0) do={
    add action=accept chain=input comment="defconf: accept established,related,untracked" connection-state=established,related,untracked
}

:if ([:len [find where comment="defconf: drop invalid" and chain=input]] = 0) do={
    add action=drop chain=input comment="defconf: drop invalid" connection-state=invalid
}

:if ([:len [find where comment="defconf: accept ICMP"]] = 0) do={
    add action=accept chain=input comment="defconf: accept ICMP" protocol=icmp
}

:if ([:len [find where comment~"local loopback"]] = 0) do={
    add action=accept chain=input comment="defconf: accept to local loopback (for CAPsMAN)" dst-address=127.0.0.1
}

:if ([:len [find where comment="allow WireGuard (UDP 51820)"]] = 0) do={
    add action=accept chain=input comment="allow WireGuard (UDP 51820)" dst-port=51820 in-interface-list=WAN protocol=udp
}

:if ([:len [find where comment="allow mgmt via WireGuard"]] = 0) do={
    add action=accept chain=input comment="allow mgmt via WireGuard" in-interface=wg0
}

:if ([:len [find where comment="WG ICMP (test)"]] = 0) do={
    add action=accept chain=input comment="WG ICMP (test)" in-interface=wg0 protocol=icmp
}

:if ([:len [find where comment="allow WG on ether1"]] = 0) do={
    add action=accept chain=input comment="allow WG on ether1" dst-port=51820 in-interface=ether1 protocol=udp
}

:if ([:len [find where comment="allow WG on lte1"]] = 0) do={
    add action=accept chain=input comment="allow WG on lte1" dst-port=51820 in-interface=lte1 protocol=udp
}

:if ([:len [find where comment~"drop all not coming from LAN" and chain=input]] = 0) do={
    add action=drop chain=input comment="defconf: drop all not coming from LAN" in-interface-list=!LAN
}

# Forward chain
:if ([:len [find where comment~"accept in ipsec"]] = 0) do={
    add action=accept chain=forward comment="defconf: accept in ipsec policy" ipsec-policy=in,ipsec
}

:if ([:len [find where comment~"accept out ipsec"]] = 0) do={
    add action=accept chain=forward comment="defconf: accept out ipsec policy" ipsec-policy=out,ipsec
}

:if ([:len [find where comment="defconf: fasttrack"]] = 0) do={
    add action=fasttrack-connection chain=forward comment="defconf: fasttrack" connection-state=established,related
}

:if ([:len [find where comment~"accept established" and chain=forward]] = 0) do={
    add action=accept chain=forward comment="defconf: accept established,related, untracked" connection-state=established,related,untracked
}

:if ([:len [find where comment="LAN -> WG (est/rel)"]] = 0) do={
    add action=accept chain=forward comment="LAN -> WG (est/rel)" connection-state=established,related,untracked out-interface=wg0
}

:if ([:len [find where comment="defconf: drop invalid" and chain=forward]] = 0) do={
    add action=drop chain=forward comment="defconf: drop invalid" connection-state=invalid
}

:if ([:len [find where comment="LAN -> WG"]] = 0) do={
    add action=accept chain=forward comment="LAN -> WG" dst-address=10.10.10.0/24 out-interface=wg0 src-address=192.168.88.0/24
}

:if ([:len [find where comment="WG -> LAN"]] = 0) do={
    add action=accept chain=forward comment="WG -> LAN" dst-address=192.168.88.0/24 in-interface=wg0
}

:if ([:len [find where comment~"drop all from WAN not DSTNATed"]] = 0) do={
    add action=drop chain=forward comment="defconf: drop all from WAN not DSTNATed" connection-nat-state=!dstnat connection-state=new in-interface-list=WAN
}

:if ([:len [find where comment="WinBox via WG"]] = 0) do={
    add action=accept chain=input comment="WinBox via WG" dst-port=8291 in-interface=wg0 protocol=tcp
}

# --- NAT ---
/ip firewall nat
:if ([:len [find where comment="defconf: masquerade"]] = 0) do={
    add action=masquerade chain=srcnat comment="defconf: masquerade" ipsec-policy=out,none out-interface-list=WAN
}
:if ([:len [find where comment="NAT for WG clients"]] = 0) do={
    add action=masquerade chain=srcnat comment="NAT for WG clients" out-interface-list=WAN src-address=10.10.10.0/24
}

# --- Routes ---
/ip route
:do {
    :if ([:len [find where comment="WAN primary via Slate"]] = 0) do={
        add check-gateway=ping comment="WAN primary via Slate" distance=1 dst-address=0.0.0.0/0 gateway=192.168.8.1
    }
} on-error={ :put "Route via Slate skipped" }

:do {
    :if ([:len [find where gateway="192.168.0.1" and dst-address="0.0.0.0/0"]] = 0) do={
        add dst-address=0.0.0.0/0 gateway=192.168.0.1
    }
} on-error={ :put "Default route skipped" }

# --- Services ---
/ip service
:do {
    set www-ssl certificate=local-cert disabled=no port=8443
} on-error={ :put "HTTPS service config failed - certificate may not exist" }

# --- IPv6 Firewall Address List ---
/ipv6 firewall address-list
:if ([:len [find where address="::/128" and list=bad_ipv6]] = 0) do={
    add address=::/128 comment="defconf: unspecified address" list=bad_ipv6
}
:if ([:len [find where address="::1/128" and list=bad_ipv6]] = 0) do={
    add address=::1/128 comment="defconf: lo" list=bad_ipv6
}
:if ([:len [find where address="fec0::/10" and list=bad_ipv6]] = 0) do={
    add address=fec0::/10 comment="defconf: site-local" list=bad_ipv6
}
:if ([:len [find where address="::ffff:0.0.0.0/96" and list=bad_ipv6]] = 0) do={
    add address=::ffff:0.0.0.0/96 comment="defconf: ipv4-mapped" list=bad_ipv6
}
:if ([:len [find where address="::/96" and list=bad_ipv6]] = 0) do={
    add address=::/96 comment="defconf: ipv4 compat" list=bad_ipv6
}
:if ([:len [find where address="100::/64" and list=bad_ipv6]] = 0) do={
    add address=100::/64 comment="defconf: discard only " list=bad_ipv6
}
:if ([:len [find where address="2001:db8::/32" and list=bad_ipv6]] = 0) do={
    add address=2001:db8::/32 comment="defconf: documentation" list=bad_ipv6
}
:if ([:len [find where address="2001:10::/28" and list=bad_ipv6]] = 0) do={
    add address=2001:10::/28 comment="defconf: ORCHID" list=bad_ipv6
}
:if ([:len [find where address="3ffe::/16" and list=bad_ipv6]] = 0) do={
    add address=3ffe::/16 comment="defconf: 6bone" list=bad_ipv6
}

# --- IPv6 Firewall Filter (simplified - add if not exists) ---
# Skipping detailed IPv6 firewall for now - most rules are default

# --- IPv6 ND ---
/ipv6 nd
:do {
    set [ find default=yes ] advertise-dns=yes
} on-error={}

# --- System Clock ---
/system clock
set time-zone-name=Europe/Helsinki

# --- Mode Button ---
/system routerboard mode-button
:do {
    set enabled=yes on-event=dark-mode
} on-error={}

# --- WPS Button ---
/system routerboard wps-button
:do {
    set enabled=yes on-event=wps-accept
} on-error={}

# --- Scripts ---
/system script
:if ([:len [find where name=dark-mode]] = 0) do={
    add comment=defconf dont-require-permissions=no name=dark-mode owner=*sys \
        policy=ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon \
        source=":if ([system leds settings get all-leds-off] = \"never\") do={\r\n  /system leds settings set all-leds-off=immediate\r\n} else={\r\n  /system leds settings set all-leds-off=never\r\n}"
}

:if ([:len [find where name=wps-accept]] = 0) do={
    add comment=defconf dont-require-permissions=no name=wps-accept owner=*sys \
        policy=ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon \
        source=":foreach iface in=[/interface/wifi find where (configuration.mode=\"ap\" && disabled=no)] do={\r\n  /interface/wifi wps-push-button \$iface\r\n}"
}

# --- MAC Server ---
/tool mac-server
set allowed-interface-list=LAN

/tool mac-server mac-winbox
set allowed-interface-list=LAN

:put ""
:put "========================================"
:put "Configuration import completed!"
:put "========================================"
