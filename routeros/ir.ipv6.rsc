# Country: Iran (IR)
# Type: IPv6
# Last updated: 2026-04-25T14:34:35Z
# Hash: sha256:8f2e2448c8497438bec11ae762c12fb2da241f20395357b9fe898caef0915df1

/ipv6 firewall address-list remove [/ipv6 firewall address-list find list=IRv6]
/ipv6 firewall address-list
:do { add address=2001:4188::/48 list=IRv6} on-error={}
:do { add address=2001:4188:1b::/48 list=IRv6} on-error={}
:do { add address=2a01:e140::/48 list=IRv6} on-error={}
:do { add address=2a01:e140:10::/44 list=IRv6} on-error={}
:do { add address=2a03:5840:13e::/48 list=IRv6} on-error={}
:do { add address=2a04:2f00:d::/48 list=IRv6} on-error={}
:do { add address=2a04:2f00:e::/48 list=IRv6} on-error={}
:do { add address=2a04:aa00::/32 list=IRv6} on-error={}
:do { add address=2a05:5440::/32 list=IRv6} on-error={}
:do { add address=2a05:9080:14::/48 list=IRv6} on-error={}
:do { add address=2a05:a380::/29 list=IRv6} on-error={}
:do { add address=2a05:cd00::/32 list=IRv6} on-error={}
:do { add address=2a06:de06:385::/48 list=IRv6} on-error={}
:do { add address=2a0c:a7c7::/40 list=IRv6} on-error={}
:do { add address=2a0d:4ac0::/40 list=IRv6} on-error={}
:do { add address=2a14:7c0:6000::/40 list=IRv6} on-error={}
:do { add address=2a14:5ac0::/32 list=IRv6} on-error={}
:do { add address=2a14:9e00:200::/40 list=IRv6} on-error={}
