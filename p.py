#!/usr/bin/env python3
import os
import sys
import time
import socket
import ipaddress
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, SpinnerColumn, MofNCompleteColumn
from rich.live import Live
from rich import box
import dns.resolver
import threading
import json
import random
import uuid
import httpx
import string
from functools import lru_cache
from datetime import datetime, timedelta

console = Console(
    force_terminal=True,
    width=120,
    highlight=False,
    soft_wrap=False
)

KEY_FILE = "keys.json"
OWNER_PASSWORD = "ALONE-OWNER"
SESSION_FILE = ".alone_session"

# Lock for safe console logging across multiple threads
print_lock = threading.Lock()

def check_device_status():
    data = load_keys()

    console.print("\n[bold cyan]── DEVICE STATUS ──[/bold cyan]")

    for key, value in data["keys"].items():
        used = len(value.get("used_devices", []))
        limit = value.get("devices", 1)

        console.print(f"[yellow]{key}[/yellow] ➜ {used}/{limit} devices used")
        
def save_session(key, expiry):
    data = {
        "key": key,
        "expiry": expiry.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(SESSION_FILE, "w") as f:
        json.dump(data, f)


def load_session():
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE, "r") as f:
            return json.load(f)
    except:
        return None

def is_owner():
    saved = load_session()
    if saved and isinstance(saved, dict):
        return saved.get("key") == OWNER_PASSWORD
    if isinstance(saved, str):
        return saved == OWNER_PASSWORD
    return False

def load_keys():
    if not os.path.exists(KEY_FILE):
        with open(KEY_FILE, "w") as f:
            json.dump({"keys": {}}, f)

    with open(KEY_FILE, "r") as f:
        return json.load(f)

def save_keys(data):
    with open(KEY_FILE, "w") as f:
        json.dump(data, f, indent=4)

def generate_key():
    p1 = ''.join(random.choice(string.ascii_uppercase) for _ in range(5))
    p2 = ''.join(random.choice(string.ascii_uppercase) for _ in range(6))
    p3 = ''.join(random.choice(string.ascii_uppercase) for _ in range(6))

    return f"ALONE-{p1}-{p2}-{p3}"

def get_device_id():
    return str(uuid.getnode())

def create_new_key():
    pwd = input("Enter Owner Password: ").strip()

    if pwd != OWNER_PASSWORD:
        console.print("[bold red]❌ Invalid Owner Password[/bold red]")
        return

    days = input("Enter Key Validity Days: ").strip()
    devices = input("Enter Device Limit: ").strip()

    try:
        devices = int(devices)
    except:
        console.print("[bold red]❌ Invalid device limit[/bold red]")
        return

    try:
        days = int(days)
    except:
        console.print("[bold red]❌ Invalid number[/bold red]")
        return

    key = generate_key()

    expiry = (
        datetime.now() + timedelta(days=days)
    ).strftime("%Y-%m-%d %H:%M:%S")

    data = load_keys()

    data["keys"][key] = {
        "expiry": expiry,
        "devices": devices,
        "used_devices": []
    }
    save_keys(data)

    console.print(
        f"\n[bold green]✅ KEY GENERATED[/bold green]\n"
    )

    console.print(
        f"[bold yellow]{key}[/bold yellow]"
    )

    console.print(
        f"[bold cyan]⏳ VALIDITY:[/bold cyan] {days} Days"
    )

    console.print(
        f"[bold magenta]📅 EXPIRES:[/bold magenta] {expiry}\n"
    )
    input("\nPress Enter To Continue...")

def check_device_status():
    data = load_keys()
    console.print("\n[bold cyan]── DEVICE STATUS CHECK ──[/bold cyan]\n")

    for key, value in data["keys"].items():
        used = len(value.get("used_devices", []))
        limit = value.get("devices", 1)

        console.print(
            f"[bold yellow]{key}[/bold yellow] → {used}/{limit}"
        )

    input("\nPress Enter to continue...")

def verify_license():
    banner()

    saved = load_session()
    data = load_keys()

    # =========================
    # AUTO LOGIN MODE
    # =========================
    if saved and isinstance(saved, dict):
        key = saved.get("key")
        expiry_str = saved.get("expiry")

        if key == OWNER_PASSWORD:
            return True

        if key in data["keys"]:
            try:
                expiry = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
            except:
                return False

            if datetime.now() > expiry:
                console.print("[bold red]❌ SESSION EXPIRED - LOGIN AGAIN[/bold red]")
                if os.path.exists(SESSION_FILE):
                    os.remove(SESSION_FILE)
                return False

            console.print("[bold bright_green]⚡ AUTO LOGIN SUCCESS (SESSION FOUND)[/bold bright_green]")
            time.sleep(1)
            return True
    # =========================
    # MANUAL LOGIN
    # =========================
    console.print("[bold bright_cyan]╔═════════════════ LICENSE AUTH ═════════════════╗[/bold bright_cyan]\n")

    user_key = input("Enter License Key: ").strip()

    # OWNER LOGIN
    if user_key == OWNER_PASSWORD:
        console.print("[bold bright_green]👑 OWNER ACCESS GRANTED[/bold bright_green]")
        save_session(OWNER_PASSWORD, datetime.now() + timedelta(days=9999))
        time.sleep(1)
        return True

    # INVALID KEY
    if user_key not in data["keys"]:
        console.print("[bold red]❌ Invalid License Key[/bold red]")
        return False

    key_data = data["keys"][user_key]

    expiry = datetime.strptime(key_data["expiry"], "%Y-%m-%d %H:%M:%S")

    if datetime.now() > expiry:
        console.print("[bold red]❌ Key Expired[/bold red]")
        return False

    # DEVICE CHECK
    current_device = get_device_id()

    if "used_devices" not in key_data:
        key_data["used_devices"] = []

    if current_device not in key_data["used_devices"]:
        if len(key_data["used_devices"]) >= key_data.get("devices", 1):
            console.print("[bold red]❌ Device Limit Reached[/bold red]")
            return False

        key_data["used_devices"].append(current_device)
        save_keys(data)

    # SAVE SESSION
    save_session(user_key, expiry)

    console.print("[bold bright_green]✅ LOGIN SUCCESS[/bold bright_green]")
    

    remaining = expiry - datetime.now()
    used = len(key_data["used_devices"])
    limit = key_data["devices"]

    console.print(
    f"[bold cyan]📱 DEVICES USED:[/bold cyan] {used}/{limit}"
    )

    console.print(
        f"\n[bold green]✅ LICENSE VERIFIED[/bold green]\n"
    )

    console.print(
        f"[bold cyan]🔑 KEY:[/bold cyan] {user_key}"
    )

    console.print(
        f"[bold yellow]⏳ VALIDITY LEFT:[/bold yellow] {remaining.days} Days"
        )
    console.print(
        f"[bold cyan]📱 DEVICES USED:[/bold cyan] "
        f"{len(key_data['used_devices'])}/{key_data['devices']}"
    )
    console.print(
        f"[bold magenta]📅 EXPIRES:[/bold magenta] {expiry}"
    )

    save_session(user_key, expiry)
    
    time.sleep(1.5)

    return True

console = Console(force_terminal=True)

# ULTRA-PREMIUM: Dynamic Cyber-Pulse Animation Core Registration
from rich.spinner import SPINNERS
SPINNERS["cyber_pulse"] = {
    "frames": [
        "🧬 [◢ ⚡ ◣]", 
        "🧬 [◣ ⚡ ◤]", 
        "🧬 [◤ ⚡ ◢]", 
        "🧬 [◤ ⚡ ◣]"
    ],
    "interval": 80
}

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AloneVoltScanner/9.9-ULTRA-GODMODE"})
adapter = requests.adapters.HTTPAdapter(pool_connections=10000, pool_maxsize=20000, max_retries=0)
session.mount('http://', adapter)
session.mount('https://', adapter)
requests.packages.urllib3.disable_warnings()

def expiry_display():
    try:
        data = load_keys()
        saved = load_session()
        if is_owner():
            return "GODMODE ACTIVE (OWNER)"
        if saved and isinstance(saved, dict):
            key = saved.get("key")
            if key in data["keys"]:
                return data["keys"][key]["expiry"]
        return "NO LICENSE"
    except:
        return "OWNER MODE"
    
def banner():
    os.system('clear' if os.name != 'nt' else 'cls')
    console.print(Panel(
        "[bold bright_cyan]  █████╗ ██╗      ██████╗ ███╗   ██╗███████╗    ██████╗ ██████╗ ██████╗ [/bold bright_cyan]\n"
        "[bold bright_cyan] ██╔══██╗██║     ██╔═══██╗████╗  ██║██╔════╝   ██╔════╝██╔════╝██╔══██╗[/bold bright_cyan]\n"
        "[bold bright_magenta] ███████║██║     ██║   ██║██╔██╗ ██║█████╗     ╚█████╗ ██║     ███████║[/bold bright_magenta]\n"
        "[bold bright_magenta] ██╔══██║██║     ██║   ██║██║╚██╗██║██╔══╝      ╚═══██╗██║     ██╔══██║[/bold bright_magenta]\n"
        "[bold bright_blue] ██║  ██║███████╗╚██████╔╝██║ ╚████║███████╗   ██████╔╝╚██████╗██║  ██║[/bold bright_blue]\n"
        "[bold bright_blue] ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝   ╚═════╝  ╚═════╝╚═╝  ╚═╝[/bold bright_blue]\n"
        "\n"
        "[bold white on red]   ⚡ UNLIMITED SCANNER | 150+ COMPLETE CDN MATRIX | ASYNC GOD MODE CORE ⚡ [/bold white on red]\n"
        "[bold bright_red]            ALONE VOLT ULTRA PREMIUM v9.9 - SPECIAL VIP EDITION[/bold bright_red]\n"
        "[bold bright_yellow]       Dev > @Alonee_op  ||  Channel > tntnetwork[/bold bright_yellow]\n"
        "[bold bright_cyan]       Link :- https://t.me/+wLK7-JgRErE4NDBl[/bold bright_cyan]\n"
        f"[bold bright_green]       🔐 License Expiry : {expiry_display()}[/bold bright_green]",
        title="[bold gold1] 【 ALONE ENGINE ARCHITECT 】 [/bold gold1]",
        border_style="bright_blue",
        box=box.ROUNDED,
        padding=(1, 2)
        
    ))
    console.print("[dim]" + "═" * 100 + "[/dim]")
       
def premium_home():
    banner()
    console.print("[bold bright_cyan]╠═══════════════════════════════ 【 VIP ACCESS GRANTED 】 ═══════════════════════════════╣[/bold bright_cyan]\n")
    console.print("[dim]" + "═" * 100 + "[/dim]")
@lru_cache(maxsize=10000)
def get_real_ip(domain):
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = ['1.1.1.1', '8.8.8.8', '9.9.9.9']
    resolver.timeout = 3
    resolver.lifetime = 3
    try:
        answers = resolver.resolve(domain, 'A')
        return str(answers[0])
    except:
        try:
            return socket.gethostbyname(domain)
        except:
            return "N/A"

def get_cdn_info(headers, server, real_ip=""):
    if not headers and not server:
        return "Origin Server"

    s = str(server).lower()
    header_keys = [str(k).lower() for k in headers.keys()]
    header_vals = [str(v).lower() for v in headers.values()]
    h_str = " ".join(header_keys + header_vals + [s])

    if real_ip.startswith("184.") or real_ip.startswith("23."):
       return "Akamai"
    signatures = [
        # =========================
        # GLOBAL CDNs
        # =========================
        (["cf-ray", "cf-cache-status", "cf-connecting-ip", "cloudflare"], "Cloudflare"),
        (["x-amz-cf-id", "x-amz-cf-pop", "cloudfront"], "CloudFront"),
        (["akamai", "edgesuite", "edgekey", "akamaighost"], "Akamai"),
        (["fastly", "x-served-by", "x-cache"], "Fastly"),
        (["stackpath"], "StackPath"),
        (["verizon", "edgecast"], "Edgecast / Verizon"),
        (["azureedge", "azure"], "Azure CDN"),
        (["bunnycdn", "bunny.net", "b-cdn"], "BunnyCDN"),
        (["cdn77"], "CDN77"),
        (["keycdn"], "KeyCDN"),
        (["limelight", "llnw"], "Limelight"),
        (["cachefly"], "CacheFly"),
        (["cdnvideo"], "CDNvideo"),
        (["gcore", "g-core"], "G-Core Labs"),
        (["arvancloud"], "ArvanCloud"),
        (["volt"], "Volt Infrastructure"),
        (["cdnetworks"], "CDNetworks"),
        (["edgio"], "Edgio"),
        (["maxcdn", "bootstrapcdn"], "MaxCDN"),
        (["quic.cloud", "litespeed"], "QUIC.cloud / LiteSpeed CDN"),
        (["section.io"], "Section.io"),
        (["fly.io"], "Fly.io"),
        (["vercel"], "Vercel"),
        (["netlify"], "Netlify"),

        # =========================
        # SECURITY / WAF
        # =========================
        (["imperva", "incapsula"], "Imperva"),
        (["sucuri"], "Sucuri"),
        (["f5", "big-ip"], "F5 BIG-IP"),
        (["radware"], "Radware WAF"),
        (["barracuda"], "Barracuda WAF"),
        (["fortinet"], "Fortinet WAF"),
        (["checkpoint"], "CheckPoint"),
        (["aws-waf"], "AWS WAF"),
        (["modsecurity", "mod_security"], "ModSecurity"),
        (["wallarm"], "Wallarm"),
        (["reblaze"], "Reblaze"),
        (["cloudbric"], "Cloudbric"),
        (["dosarrest"], "DOSarrest"),
        (["sitelock"], "SiteLock"),
        (["citrix", "netscaler"], "Citrix NetScaler"),
        (["stormwall", "blazingfast"], "StormWall / BlazingFast"),

        # =========================
        # CLOUD PROVIDERS
        # =========================
        (["amazonaws", "x-amz"], "AWS"),
        (["google", "gcp", "googleusercontent"], "Google Cloud"),
        (["digitalocean"], "DigitalOcean"),
        (["linode"], "Linode"),
        (["vultr"], "Vultr"),
        (["ovh"], "OVH Cloud"),
        (["hetzner"], "Hetzner"),
        (["oracle", "oci"], "Oracle Cloud"),
        (["alibaba", "aliyun"], "Alibaba Cloud"),
        (["tencent"], "Tencent Cloud"),
        (["huawei"], "Huawei Cloud"),
        (["ibmcloud"], "IBM Cloud"),
        (["azure"], "Microsoft Azure"),
        (["scaleway"], "Scaleway"),
        (["contabo"], "Contabo"),
        (["upcloud"], "UpCloud"),

        # =========================
        # HOSTING / PLATFORMS
        # =========================
        (["shopify"], "Shopify"),
        (["squarespace"], "Squarespace"),
        (["wix"], "Wix"),
        (["webflow"], "Webflow"),
        (["wpengine"], "WPEngine"),
        (["kinsta"], "Kinsta"),
        (["cloudways"], "Cloudways"),
        (["siteground"], "SiteGround"),
        (["hostgator"], "HostGator"),
        (["hostinger"], "Hostinger"),
        (["bluehost"], "Bluehost"),
        (["godaddy"], "GoDaddy"),
        (["namecheap"], "Namecheap"),
        (["heroku"], "Heroku"),
        (["render"], "Render"),
        (["railway"], "Railway"),
        (["firebase"], "Firebase Hosting"),
        (["github.io"], "GitHub Pages"),
        (["gitlab.io"], "GitLab Pages"),

        # =========================
        # TELECOM / NETWORKS
        # =========================
        (["jiocdn"], "Jio CDN"),
        (["airtel"], "Airtel"),
        (["tata", "vsnl"], "Tata Communications"),
        (["ntt"], "NTT"),
        (["telstra"], "Telstra"),
        (["singtel"], "Singtel"),
        (["comcast"], "Comcast"),
        (["t-mobile"], "T-Mobile"),
        (["vodafone"], "Vodafone"),
        (["orange"], "Orange Telecom"),

        # =========================
        # WEB SERVERS
        # =========================
        (["nginx"], "Nginx"),
        (["apache"], "Apache HTTP Server"),
        (["openresty"], "OpenResty"),
        (["iis"], "IIS Server"),
        (["litespeed"], "LiteSpeed"),
        (["caddy"], "Caddy"),
        (["envoy"], "Envoy Proxy"),
        (["haproxy"], "HAProxy"),
        (["varnish"], "Varnish Cache"),
        (["node", "express"], "Node.js / Express"),

        # =========================
        # SPECIAL / EDGE CASES
        # =========================
        (["jsdelivr"], "jsDelivr"),
        (["cdnjs"], "cdnjs"),
        (["unpkg"], "unpkg"),
        (["volt"], "Volt Infrastructure"),
    ]

    for keywords, name in signatures:
        if any(kw in h_str for kw in keywords):
            return name

    if "cdn" in h_str: return "Generic CDN"
    if "waf" in h_str: return "Generic WAF"
    if "edge" in h_str or "cache" in h_str: return "Generic Edge Network"
    if "nginx" in s: return "Nginx"
    if "apache" in s: return "Apache"
    if "iis" in s: return "IIS Server"
    return "Origin Server"
    
def check_target_fixed(target, proto, port):
    clean_target = str(target).replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
    real_ip = clean_target if clean_target.replace('.','').isdigit() else get_real_ip(clean_target)
    
    if real_ip == "N/A":
        return None

    try:
        url = f"{proto}://{clean_target}:{port}"

        with httpx.Client(
            timeout=httpx.Timeout(5.0),
            verify=False,
            http2=True,
            follow_redirects=True,
            max_redirects=5,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AloneVoltScanner/9.9-ULTRA"
            }
        ) as client:

            r = client.get(url)
            code = r.status_code

            # REAL HTTP VERSION
            proto_ver = "HTTP/2" if getattr(r, 'http_version', 11) == 20 else "HTTP/1.1"

            # STATUS TEXT
            status_text = httpx.codes.get_reason_phrase(code)

            full_status = f"{proto_ver} {code} {status_text}"
            status_padded = f"[{full_status}]"

            server = r.headers.get(
                "server",
                r.headers.get("x-powered-by", "Unknown")
            )

            cdn = get_cdn_info(r.headers, server, real_ip)
 
            line = (
                f"{status_padded} │ "
                f"{clean_target} │ "
                f"{real_ip} │ "
                f"{cdn}"
            )
            
            return (target, real_ip, code, cdn, True, line)

    except Exception:
        return None
            
    
def get_port_and_proto():
    console.print("\n[bold magenta]┌───┤ TARGET PORT CONFIGURATION ├───┐[/bold magenta]")
    port = input(" │ Enter Port to test (80, 443, 8080): ").strip()
    if not port:
        port = "80"
    
    if port == "80":
        proto = "http"
    elif port == "443":
        proto = "https"
    else:
        proto_choice = input(" │ Enter protocol for custom port (http/https): ").strip().lower()
        proto = "https" if proto_choice == "https" else "http"
    console.print("[bold magenta]└───────────────────────────────────┘[/bold magenta]")        
    return proto, port

def scan_targets(targets, proto, port, scan_name="ALONE SCAN", threads=2500):
    counter = 0
    banner()
    start_time = time.time()

    console.print(
        Panel(
            f"[bold gold1]⚡ VIP ASYNC ENGINE: RUNNING │ DATA MOD: {scan_name} │ TARGETS: {len(targets):,} [/bold gold1]",
            border_style="bright_cyan"
        )
    )

    results = []
    found_200 = 0
    total = len(targets)

    if os.path.exists("/sdcard"):
        downloads_path = "/sdcard/Download"
    else:
        downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")

    os.makedirs(downloads_path, exist_ok=True)

    output_file = os.path.join(
        downloads_path,
        f"alone_live_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )

    max_workers = min(threads, 2500, len(targets)//2 + 1000)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("=== ALONE VOLT SCANNER v9.9 ULTRA REPORT ===\n")
        f.write(f"Time: {datetime.now()}\n\n")

        progress = Progress(
            SpinnerColumn(spinner_name="cyber_pulse", style="bold bright_green"),
            TextColumn(f"[bold bright_magenta]┋ SCANNING ({proto.upper()}) ┋[/bold bright_magenta]"),
            BarColumn(
                bar_width=45,
                style="bright_black",
                complete_style="bold bright_cyan",
                finished_style="bold bright_green"
            ),
            MofNCompleteColumn(),
            TextColumn("[bold bright_yellow][{task.percentage:>3.0f}%][/bold bright_yellow]"),
            TextColumn("[bold white]⏳ TIME REMAINING:[/bold white]"),
            TimeRemainingColumn(),
            console=console
        )

        with progress:
            task = progress.add_task(
                f"[bold white]Firing Core Cluster Ports [{port}]...[/bold white]",
                total=total
            )

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_target = {
                    executor.submit(check_target_fixed, t, proto, port): t
                    for t in targets
                }

                for future in as_completed(future_to_target):
                    try:
                        result = future.result()
                    except Exception:
                        progress.advance(task)
                        continue

                    progress.advance(task)

                    if not result:
                        continue

                    target, real_ip, code, cdn, is_alive, line = result

                    # ================= FIXED BLOCK =================
                    counter += 1
                    serial = counter

                    with print_lock:
                        f.write(f"{serial}. {line}\n")
                        f.flush()

                        if code == 200:
                            console.print(f"[bold cyan][{serial}] │ {line}")
                            console.print("[dim]" + "─" * 100 + "[/dim]")
                            found_200 += 1

                        elif code == 403:
                            console.print(f"[bold bright_magenta][{serial}] [403 Forbidden] {line}[/bold bright_magenta]")
                            console.print("[dim]" + "─" * 100 + "[/dim]")

                        elif code == 503:
                            console.print(f"[bold bright_yellow][{serial}] ⚠️ [503 Service Unavailable] {line}[/bold bright_yellow]")

                        elif code == 502:
                            console.print(f"[bold bright_yellow][{serial}] ⚠️ [502 Bad Gateway] {line}[/bold bright_yellow]")

                        elif code == 504:
                            console.print(f"[bold bright_yellow][{serial}] ⚠️ [504 Gateway Timeout] {line}[/bold bright_yellow]")

                        elif code == 429:
                            console.print(f"[bold bright_red][{serial}] [429 Too Many Requests] {line}[/bold bright_red]")

                        elif code in [301, 302, 307, 308]:
                            console.print(f"[bold bright_blue][{serial}] [{code} Redirect] {line}[/bold bright_blue]")

                        elif code >= 500:
                            console.print(f"[bold bright_red][{serial}] [{code}] {line}[/bold bright_red]")

                        elif code >= 400:
                            console.print(f"[bold bright_magenta][{serial}] [{code}] {line}[/bold bright_magenta]")

                        else:
                            console.print(f"[bold cyan][{serial}] [{code}] {line}[/bold cyan]")
                            console.print("[dim]────────────────────────────────────────────[/dim]")

                    results.append(line)
                    # ================= END FIX =================

    try:
        duration = str(timedelta(seconds=int(time.time() - start_time)))

        banner()
        console.print(
            Panel(
                f" [🛸] Total Targets Scanned : [bold bright_cyan]{total:<8}[/bold bright_cyan]\n"
                f" [🎯] Targeted Port Protocol : [bold bright_blue]{port} ({proto.upper()})[/bold bright_blue]\n"
                f" [🔥] Live Hits (200 OK)    : [bold bright_green]{found_200:<8}[/bold bright_green]\n"
                f" [📊] Intercept Database    : [bold bright_yellow]{len(results):<8}[/bold bright_yellow]\n"
                f" [⏱️] Execution Duration    : [bold bright_magenta]{duration}[/bold bright_magenta]\n"
                f" [📁] Encrypted Output Path : [bold bright_green]{output_file}[/bold bright_green]",
                title="[bold bright_green] 【 CRITICAL MATRIX REPORT COMPLETED 】 [/bold bright_green]",
                border_style="bright_green",
                box=box.DOUBLE
            )
        )

        input("\n[bold blink bright_green]» Press Enter to return to main dashboard...[/bold blink bright_green]")

    except Exception as e:
        console.print(f"[bold red]⚠️ Final panel forced fallback: {e}[/bold red]")
        input("\nPress Enter...")

def single_domain_scan():
    banner()
    console.print("[bold bright_blue]───┤ [🎯] SINGLE TARGET STRATEGIC PROFILER ├───[/bold bright_blue]\n")
    target = input("Enter single domain/IP: ").strip()
    if target:
        proto, port = get_port_and_proto()
        scan_targets([target], proto, port, "SINGLE TARGET PRO", 100)

def txt_scan():
    banner()
    console.print("[bold bright_green]───┤ [📂] BATCH TEXT DATABASE LOADER ├───[/bold bright_green]\n")
    path = input("Enter targets .txt file path: ").strip()
    if not os.path.exists(path):
        console.print("[bold red]❌ Target file path not resolved![/bold red]")
        time.sleep(1.5)
        return
    with open(path, 'r', encoding='utf-8') as f:
        targets = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    console.print(f"[bold bright_green]✓ Loaded {len(targets):,} targets[/bold bright_green]")
    
    proto, port = get_port_and_proto()
    
    threads = int(input("\nEnter Concurrency Pipeline Throttle (500-3500): ") or "1800")
    scan_targets(targets, proto, port, "MASSIVE TXT ENGINE", threads)

def cidr_scan():
    banner()
    console.print("[bold bright_magenta]───┤ [🌐] CIDR NETWORK GENERATOR ENGINE ├───[/bold bright_magenta]\n")

    cidr = input("Enter CIDR Subnet Block: ").strip()
    if not cidr:
        console.print("[bold red]❌ CIDR Block खाली नहीं छोड़ सकते![/bold red]")
        time.sleep(1.5)
        return

    try:
        network = ipaddress.ip_network(cidr, strict=False)
        targets = [str(ip) for ip in network.hosts()]
        console.print(f"[bold bright_green]✓ Generated {len(targets):,} hosts[/bold bright_green]")
    except Exception as e:
        console.print(f"[bold red]❌ Invalid CIDR Structure: {e}[/bold red]")
        time.sleep(2)
        return

    proto, port = get_port_and_proto()
    
    try:
        threads_input = input("\nEnter Concurrency Pipeline Throttle (500-3500, Default 1800): ").strip()
        threads = int(threads_input) if threads_input else 1800
    except ValueError:
        threads = 1800

    scan_targets(targets, proto, port, f"CIDR Block: {cidr}", threads)

# =========================
# MAIN MENU
# =========================
def main_menu():
    while True:
        premium_home()

        console.print(
            "\n[bold bright_cyan]"
            "╔═══════════════════════════ 【 ⚡ ALONE VOLT CONTROL PANEL ⚡ 】 ═══════════════════════════╗"
            "[/bold bright_cyan]\n"
        )

        menu = [
            ("01", "bright_green",  "📂 LOAD TARGET TXT DATABASE"),
            ("02", "bright_magenta","🌐 CIDR SUBNET IP BLOCK RANGE SCANNER"),
            ("03", "bright_blue",   "🎯 SINGLE TARGET STRATEGIC PROFILER"),
            ("04", "bright_yellow", "📊 REVIEW ENGINE STATUS / PREMIUM HOME"),
            ("05", "bright_red",    "💀 KILL PROCESS / EXIT ENGINE"),
        ]

        for num, color, text in menu:
            console.print(
                f"[bold black on {color}] {num:^3} [/bold black on {color}] "
                f"[bold {color}] {text}[/bold {color}]"
            )
            
            
        console.print("\n" + "─"*95)
        session = load_session()

        if is_owner():
            console.print(" [👑 ACCESS NODE]: [bold gold1]ROOT ADMIN CORE ACTIVE[/bold gold1]")

            console.print(
                "[bold black on bright_cyan] 06 [/bold black on bright_cyan] "
                "[bold bright_cyan]🔑 CREATE LICENSE KEY[/bold bright_cyan]"
            )

            console.print(
                "[bold black on bright_blue] 07 [/bold black on bright_blue] "
                "[bold bright_blue]📱 CHECK DEVICE STATUS[/bold bright_blue]"
            )

        elif session:
            console.print(" [👤 ACCESS NODE]: [bold bright_green]VIP USER MODE GRANTED[/bold bright_green]")

        else:
            console.print(" [❌ ACCESS NODE]: [bold red]NO SESSION ENCRYPTED[/bold red]")
            
        console.print("─"*95 + "\n")


        choice = console.input(
            "\n[bold bright_green]"
            "╭─[ ⚡ SELECT OPERATION TOKEN ]\n"
            "╰─➤ "
            "[/bold bright_green]"
        ).strip()

        if choice == "1":
            txt_scan()

        elif choice == "2":
            cidr_scan()

        elif choice == "3":
            single_domain_scan()

        elif choice == "4":
            premium_home()
            input("\nDashboard verified. Press Enter...")

        elif choice == "5":
            console.print("[bold red]💀 Shutting down engine...[/bold red]")
            sys.exit(0)

        elif choice == "6":
            if not is_owner():
                console.print("[bold red]❌ OWNER ONLY ACCESS[/bold red]")
                time.sleep(1)
            else:
                create_new_key()

        elif choice == "7":
            if not is_owner():
                console.print("[bold red]❌ OWNER ONLY ACCESS[/bold red]")
                time.sleep(1)
            else:
                check_device_status()

        else:
            console.print("[bold red]❌ Invalid option[/bold red]")
            time.sleep(1)


BYPASS_LICENSE = True

if __name__ == "__main__":
    try:
        if BYPASS_LICENSE or verify_license():
            main_menu()

    except KeyboardInterrupt:
        console.print("\n[bold red]⚠️ Interrupted by user. Exiting safely...[/bold red]")

    except Exception as e:
        console.print(f"[bold red]💥 System Fault Detected: {e}[/bold red]")