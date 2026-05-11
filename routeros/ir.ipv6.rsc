# Country: Iran (IR)
# Type: IPv6
# Last updated: 2026-05-11T19:49:41Z
# Hash: sha256:71ec22d54c5456cc81f86141bbc7fc5a491dbc1cd3f529d59a8c9bc737772bd0

/ipv6 firewall address-list remove [/ipv6 firewall address-list find list=IRv6]
/ipv6 firewall address-list
:do { add address=2001:4188::/48 list=IRv6} on-error={}
:do { add address=2001:4188:1b::/48 list=IRv6} on-error={}
:do { add address=2a01:e140::/48 list=IRv6} on-error={}
:do { add address=2a01:e140:10::/44 list=IRv6} on-error={}
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
