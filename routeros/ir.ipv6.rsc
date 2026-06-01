# Country: Iran (IR)
# Type: IPv6
# Last updated: 2026-06-01T04:02:04Z
# Hash: sha256:c63697d4dd09abce5e6bd17691f3b4b14567b2ba6e697dfb888d4fd2755d8c47

/ipv6 firewall address-list remove [/ipv6 firewall address-list find list=IRv6]
/ipv6 firewall address-list
:do { add address=2001:4188::/48 list=IRv6} on-error={}
:do { add address=2001:4188:1b::/48 list=IRv6} on-error={}
:do { add address=2a01:e140::/48 list=IRv6} on-error={}
:do { add address=2a01:e140:10::/44 list=IRv6} on-error={}
:do { add address=2a02:dfc0:1::/48 list=IRv6} on-error={}
:do { add address=2a02:dfc0:2::/47 list=IRv6} on-error={}
:do { add address=2a02:dfc0:4::/48 list=IRv6} on-error={}
:do { add address=2a03:5840:13e::/48 list=IRv6} on-error={}
:do { add address=2a04:2f00:d::/48 list=IRv6} on-error={}
:do { add address=2a04:2f00:e::/48 list=IRv6} on-error={}
:do { add address=2a04:5040:6003::/48 list=IRv6} on-error={}
:do { add address=2a04:aa00::/32 list=IRv6} on-error={}
:do { add address=2a05:5440::/32 list=IRv6} on-error={}
:do { add address=2a05:9080:14::/48 list=IRv6} on-error={}
:do { add address=2a05:cd00::/32 list=IRv6} on-error={}
:do { add address=2a06:de06:385::/48 list=IRv6} on-error={}
:do { add address=2a0c:a7c6:2b::/48 list=IRv6} on-error={}
:do { add address=2a0c:a7c6:1000::/36 list=IRv6} on-error={}
:do { add address=2a0c:a7c7::/40 list=IRv6} on-error={}
:do { add address=2a0d:4ac0::/40 list=IRv6} on-error={}
:do { add address=2a14:5ac0::/32 list=IRv6} on-error={}
