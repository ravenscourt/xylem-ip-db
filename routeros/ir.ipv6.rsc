# Country: Iran (IR)
# Type: IPv6
# Last updated: 2026-07-02T08:59:16Z
# Hash: sha256:5e7308c8c1df2984bc7206a4dab210ea6aa4dd6a8b38e2404527ba58dfd754db

/ipv6 firewall address-list remove [/ipv6 firewall address-list find list=IRv6]
/ipv6 firewall address-list
:do { add address=2001:4188::/48 list=IRv6} on-error={}
:do { add address=2001:4188:1b::/48 list=IRv6} on-error={}
:do { add address=2a01:e140::/32 list=IRv6} on-error={}
:do { add address=2a02:dfc0:1::/48 list=IRv6} on-error={}
:do { add address=2a02:dfc0:2::/47 list=IRv6} on-error={}
:do { add address=2a02:dfc0:4::/48 list=IRv6} on-error={}
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
:do { add address=2a0f:9800::/29 list=IRv6} on-error={}
:do { add address=2a14:5ac0::/32 list=IRv6} on-error={}
