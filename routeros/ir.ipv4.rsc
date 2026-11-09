# Country: Iran (IR)
# Type: IPv4
# Last updated: 2026-11-09T04:51:30Z
# Hash: sha256:ec0f467f41725541f2bd9ae16d733a48e390a5da99787d3bb6fca44cb8ef877e

/ip firewall address-list remove [/ip firewall address-list find list=IRv4]
/ip firewall address-list
:do { add address=2.189.44.44/31 list=IRv4} on-error={}
:do { add address=5.160.0.0/16 list=IRv4 comment="Respina ISP"} on-error={}
:do { add address=10.0.0.0/8 list=IRv4 comment="Intranet"} on-error={}
:do { add address=46.209.0.0/16 list=IRv4 comment="Respina ISP"} on-error={}
:do { add address=77.104.64.0/18 list=IRv4 comment="Respina ISP"} on-error={}
:do { add address=100.64.0.0/10 list=IRv4 comment="Mobile Network CGNAT"} on-error={}
:do { add address=104.26.8.161/32 list=IRv4 comment="Exir Dynamic IP - pro.exir.io"} on-error={}
:do { add address=104.26.9.161/32 list=IRv4 comment="Exir Dynamic IP - pro.exir.io"} on-error={}
:do { add address=172.67.71.91/32 list=IRv4 comment="Exir Dynamic IP - pro.exir.io"} on-error={}
:do { add address=178.22.122.100/32 list=IRv4 comment="Shecan DNS"} on-error={}
:do { add address=185.51.200.2/32 list=IRv4 comment="Shecan DNS"} on-error={}
:do { add address=185.55.225.25/32 list=IRv4 comment="Begzar DNS"} on-error={}
:do { add address=185.55.226.26/32 list=IRv4 comment="Begzar DNS"} on-error={}
:do { add address=217.218.127.127/32 list=IRv4 comment="TIC DNS"} on-error={}
:do { add address=217.218.155.155/32 list=IRv4 comment="TIC DNS"} on-error={}
