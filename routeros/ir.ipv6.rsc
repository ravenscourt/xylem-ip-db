# Country: Iran (IR)
# Type: IPv6
# Last updated: 2026-11-09T04:51:30Z
# Hash: sha256:e3d2a538d9ee448b6b3a4c9444d09602a565d717d25b3ead4ecb1407816f6613

/ipv6 firewall address-list remove [/ipv6 firewall address-list find list=IRv6]
/ipv6 firewall address-list
:do { add address=2606:4700:20::681a:8a1/128 list=IRv6 comment="Exir Dynamic IP - pro.exir.io"} on-error={}
:do { add address=2606:4700:20::681a:9a1/128 list=IRv6 comment="Exir Dynamic IP - pro.exir.io"} on-error={}
:do { add address=2606:4700:20::ac43:475b/128 list=IRv6 comment="Exir Dynamic IP - pro.exir.io"} on-error={}
