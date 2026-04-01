# Xylem IP Database
IP range lists for countries with internet restrictions, sourced from [RIPE NCC](https://stat.ripe.net/) with community-maintained overrides. Lists are updated automatically every 6 hours.

Available as plain-text CIDR lists and ready-to-import RouterOS scripts.

## Available Lists
| Country | Plain Text | RouterOS | sing-box |
|---------|-----------|----------|----------|
| Iran (IR) | [`ipv4`](lists/ir.ipv4.txt) [`ipv6`](lists/ir.ipv6.txt) | [`ipv4`](routeros/ir.ipv4.rsc) [`ipv6`](routeros/ir.ipv6.rsc) | [`ipv4`](sing-box/ir.ipv4.json) [`ipv6`](sing-box/ir.ipv6.json) |
| Russia (RU) | [`ipv4`](lists/ru.ipv4.txt) [`ipv6`](lists/ru.ipv6.txt) | [`ipv4`](routeros/ru.ipv4.rsc) [`ipv6`](routeros/ru.ipv6.rsc) | [`ipv4`](sing-box/ru.ipv4.json) [`ipv6`](sing-box/ru.ipv6.json) |
| China (CN) | [`ipv4`](lists/cn.ipv4.txt) [`ipv6`](lists/cn.ipv6.txt) | [`ipv4`](routeros/cn.ipv4.rsc) [`ipv6`](routeros/cn.ipv6.rsc) | [`ipv4`](sing-box/cn.ipv4.json) [`ipv6`](sing-box/cn.ipv6.json) |

## Usage

### Raw Lists
Each `.txt` file in the [`lists/`](lists/) directory contains one CIDR range per line with a metadata header. Use these with any firewall, VPN, or routing tool that accepts CIDR notation.

Direct links:

```
https://raw.githubusercontent.com/ravenscourt/xylem-ip-db/main/lists/ir.ipv4.txt
https://raw.githubusercontent.com/ravenscourt/xylem-ip-db/main/lists/ir.ipv6.txt
```

Replace `ir` with `ru` or `cn` for other countries.

### RouterOS

#### Manual (Initial Seed / Offline Transfer)
Use the `.rsc` files for first-time setup or when transferring to a router without internet access.

1. Download the `.rsc` file for your country from the [`routeros/`](routeros/) directory.
2. Upload it to your router (WinBox drag-and-drop, SCP, or FTP).
3. Import:

```routeros
/import file-name=ir.ipv4.rsc
```

> The `.rsc` file clears the existing address list and rebuilds it. Safe to re-run.

#### Automatic Updates (Recommended)
Create a script on the router that periodically fetches the **plain-text list** and rebuilds the address list locally. This is more secure than importing `.rsc` files because only raw IP ranges are downloaded -- your router never executes foreign scripts.

**Step 1 -- Create update scripts**

IPv4 example (Iran):

```routeros
/system script add name=update-irv4 source={
  :local country "ir"
  :local listName "IRv4"
  :local fileName ($country . ".ipv4.txt")
  :local url ("https://raw.githubusercontent.com/ravenscourt/xylem-ip-db/main/lists/" . $fileName)
  :do {
    /tool fetch url=$url dst-path=$fileName mode=https
    :delay 3s
    :if ([:len [/file find name=$fileName]] > 0) do={
      :if ([/file get $fileName size] > 0) do={
        /ip firewall address-list remove [/ip firewall address-list find list=$listName]
        :local content [/file get $fileName contents]
        :local lines [:toarray $content]
        :local comment ""
        :foreach line in=$lines do={
          :if ([:len $line] = 0) do={
            :set comment ""
          } else={
            :if ([:pick $line 0 1] = "#") do={
              :set comment [:pick $line 2 [:len $line]]
            } else={
              :if ([:len $comment] > 0) do={
                :do { /ip firewall address-list add list=$listName address=$line comment=$comment } on-error={}
                :set comment ""
              } else={
                :do { /ip firewall address-list add list=$listName address=$line } on-error={}
              }
            }
          }
        }
        /file remove $fileName
        :log info "$listName address list synced successfully"
      } else={
        :log warning "Download failed or empty file - keeping old address list"
        /file remove $fileName
      }
    } else={
      :log warning "File not found after fetch - download likely failed"
    }
  } on-error={
    :log error "Failed to sync $listName address list"
  }
}
```

For IPv6, use `/ipv6 firewall address-list` instead:

```routeros
/system script add name=update-irv6 source={
  :local country "ir"
  :local listName "IRv6"
  :local fileName ($country . ".ipv6.txt")
  :local url ("https://raw.githubusercontent.com/ravenscourt/xylem-ip-db/main/lists/" . $fileName)
  :do {
    /tool fetch url=$url dst-path=$fileName mode=https
    :delay 3s
    :if ([:len [/file find name=$fileName]] > 0) do={
      :if ([/file get $fileName size] > 0) do={
        /ipv6 firewall address-list remove [/ipv6 firewall address-list find list=$listName]
        :local content [/file get $fileName contents]
        :local lines [:toarray $content]
        :local comment ""
        :foreach line in=$lines do={
          :if ([:len $line] = 0) do={
            :set comment ""
          } else={
            :if ([:pick $line 0 1] = "#") do={
              :set comment [:pick $line 2 [:len $line]]
            } else={
              :if ([:len $comment] > 0) do={
                :do { /ipv6 firewall address-list add list=$listName address=$line comment=$comment } on-error={}
                :set comment ""
              } else={
                :do { /ipv6 firewall address-list add list=$listName address=$line } on-error={}
              }
            }
          }
        }
        /file remove $fileName
        :log info "$listName address list synced successfully"
      } else={
        :log warning "Download failed or empty file - keeping old address list"
        /file remove $fileName
      }
    } else={
      :log warning "File not found after fetch - download likely failed"
    }
  } on-error={
    :log error "Failed to sync $listName address list"
  }
}
```

> Change `country` and `listName` for other countries. See the [Available Lists](#available-lists) table for values.

**Step 2 -- Schedule automatic runs**

```routeros
/system scheduler add name=schedule-irv4 interval=12h on-event="/system script run update-irv4" start-time=startup
/system scheduler add name=schedule-irv6 interval=12h on-event="/system script run update-irv6" start-time=startup
```

Adjust `interval` to your preference. `start-time=startup` ensures the list is refreshed on router boot as well.

### OpenWrt (PBR)
If you use [Policy-Based Routing (pbr)](https://docs.openwrt.melmac.net/pbr/) on OpenWrt, you can create a custom user file that fetches the IP lists and adds them to the PBR nft sets. This routes matching traffic through a specific interface (e.g. a VPN tunnel).

**Step 1 -- Create the user file**

Create `/usr/share/pbr/pbr.user.xylem` (or any name starting with `pbr.user.`):

```sh
#!/bin/sh
# Fetches xylem-ip-db lists and adds them to PBR nft sets.
# Change COUNTRY and TARGET_INTERFACE to match your setup.

COUNTRY="ir"
TARGET_INTERFACE="wg0"
TARGET_TABLE="inet fw4"
BASE_URL="https://raw.githubusercontent.com/ravenscourt/xylem-ip-db/main/lists"

for ver in 4 6; do
  url="${BASE_URL}/${COUNTRY}.ipv${ver}.txt"
  tmp="/tmp/pbr_xylem_${COUNTRY}_v${ver}.txt"
  nftset="pbr_${TARGET_INTERFACE}_${ver}_dst_ip_user"

  uclient-fetch -qO- "$url" | grep -v '^#' | grep -v '^$' > "$tmp" 2>/dev/null
  [ -s "$tmp" ] || continue

  elements=$(paste -sd, "$tmp")
  nft "add element ${TARGET_TABLE} ${nftset} { ${elements} }" 2>/dev/null
  rm -f "$tmp"
done
```

> Set `COUNTRY` to the country code you need (e.g. `ir`, `ru`, `cn`) and `TARGET_INTERFACE` to your VPN/tunnel interface. Create a separate user file for each country if needed.

**Step 2 -- Enable it in PBR config**

Via UCI:

```sh
uci add pbr include
uci set pbr.@include[-1].path='/usr/share/pbr/pbr.user.xylem'
uci set pbr.@include[-1].enabled='1'
uci commit pbr
service pbr restart
```

Or add it manually to `/etc/config/pbr`:

```
config include
  option path '/usr/share/pbr/pbr.user.xylem'
  option enabled '1'
```

The script runs automatically whenever PBR starts or reloads. IPv6 sets are only populated if `ipv6_enabled` is set to `1` in your PBR config.

### pf (FreeBSD / macOS)
The `.txt` files work directly with pf tables.

Load a list into a table:

```sh
curl -s https://raw.githubusercontent.com/ravenscourt/xylem-ip-db/main/lists/ir.ipv4.txt \
  | pfctl -t ir_ipv4 -T replace -f -
```

Reference the table in your `pf.conf`:

```
table <ir_ipv4> persist
pass out quick on egress to <ir_ipv4> route-to (tun0)
```

To auto-update, add the `curl | pfctl` command to a cron job.

### iptables + ipset (Linux)
Create a hash:net ipset and load ranges from the list:

```sh
COUNTRY="ir"
SET_NAME="ir_ipv4"
URL="https://raw.githubusercontent.com/ravenscourt/xylem-ip-db/main/lists/${COUNTRY}.ipv4.txt"

ipset create "$SET_NAME" hash:net -exist
ipset flush "$SET_NAME"
curl -s "$URL" | grep -v '^#' | grep -v '^$' | while read -r range; do
  ipset add "$SET_NAME" "$range" -exist
done
```

Then match it in iptables:

```sh
iptables -A FORWARD -m set --match-set ir_ipv4 dst -j MARK --set-mark 1
```

For IPv6, use `ipset create ir_ipv6 hash:net family inet6` and `ip6tables`.

> This also works on systems running UFW, since UFW uses iptables/netfilter under the hood. ipset rules coexist with UFW without conflict.

### nftables (Linux)

Create a named set and load ranges:

```sh
COUNTRY="ir"
SET_NAME="ir_ipv4"
URL="https://raw.githubusercontent.com/ravenscourt/xylem-ip-db/main/lists/${COUNTRY}.ipv4.txt"

nft add table inet filter 2>/dev/null
nft "add set inet filter ${SET_NAME} { type ipv4_addr; flags interval; }" 2>/dev/null
nft flush set inet filter "$SET_NAME"

elements=$(curl -s "$URL" | grep -v '^#' | grep -v '^$' | paste -sd,)
nft "add element inet filter ${SET_NAME} { ${elements} }"
```

Then reference the set in a rule:

```sh
nft add rule inet filter forward ip daddr @ir_ipv4 meta mark set 1
```

For IPv6, change the set type to `ipv6_addr` and use `ip6 daddr`.

### Clash / Mihomo
The `.txt` files work directly as [rule provider](https://wiki.metacubex.one/config/rule-providers/) sources.

Add a rule provider to your config:

```yaml
rule-providers:
  ir-ipv4:
    type: http
    behavior: ipcidr
    format: text
    url: "https://raw.githubusercontent.com/ravenscourt/xylem-ip-db/main/lists/ir.ipv4.txt"
    interval: 43200
    path: ./rules/ir-ipv4.txt

rules:
  - RULE-SET,ir-ipv4,DIRECT
```

Replace `ir` with the country code you need. For IPv6, use the `.ipv6.txt` URL.

### sing-box
Pre-built [rule sets](https://sing-box.sagernet.org/configuration/rule-set/) are available in the [`sing-box/`](sing-box/) directory in source JSON format.

Use them as remote rule sets in your config:

```json
{
  "route": {
    "rule_set": [
      {
        "tag": "ir-ipv4",
        "type": "remote",
        "format": "source",
        "url": "https://raw.githubusercontent.com/ravenscourt/xylem-ip-db/main/sing-box/ir.ipv4.json"
      }
    ],
    "rules": [
      {
        "rule_set": "ir-ipv4",
        "outbound": "direct"
      }
    ]
  }
}
```

### V2Ray / Xray

V2Ray and Xray can use inline CIDRs in routing rules for small lists, but for the large lists in this repository the recommended approach is to use a custom `geoip.dat` file. Projects like [v2ray-rules-dat](https://github.com/Loyalsoldier/v2ray-rules-dat) generate these from CIDR sources. Our `.txt` files can be used as input for such generators.

## Contributing
To request a change to a country's IP list, open an issue using the appropriate template:

- [Request an Addition](https://github.com/ravenscourt/xylem-ip-db/issues/new?template=addition_request.yml) -- add a range that RIPE is missing.
- [Request an Exemption](https://github.com/ravenscourt/xylem-ip-db/issues/new?template=exemption_request.yml) -- exclude a range that shouldn't be in the list.

### Development
Requires Python 3.13+ and [just](https://github.com/casey/just).

```sh
just setup
```

This creates a venv, installs dev dependencies, and sets up pre-commit hooks (lint + tests run automatically on each commit).

Other useful commands: `just lint`, `just fmt`, `just test`, `just check`, `just generate`.

## Acknowledgements
This project relies on data from:

- [RIPE NCC RIPEstat](https://stat.ripe.net/) -- Iranian IP ranges via ASN-based prefix resolution
- [antifilter.download](https://antifilter.download/) -- Russian IP range aggregation
- [chnroutes2](https://github.com/misakaio/chnroutes2) -- Chinese IP range list