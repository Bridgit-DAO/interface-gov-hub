# Wildcard Cert – No Manual TXT Records

Use **certbot-dns-multi** so your DNS provider’s API creates the TXT records for you.

## 1. Install certbot-dns-multi

```bash
sudo snap install certbot-dns-multi
sudo snap set certbot trust-plugin-with-root=ok
sudo snap connect certbot:plugin certbot-dns-multi
```

## 2. Create credentials file

**Vultr** (if themetalayer.org DNS is on Vultr):
```bash
sudo tee /etc/letsencrypt/dns-multi.ini << 'EOF'
dns_multi_provider = vultr
VULTR_API_KEY = your_api_key_here
EOF
sudo chmod 600 /etc/letsencrypt/dns-multi.ini
```
Get API key: Vultr Dashboard → Account → API

**DigitalOcean**:
```bash
sudo tee /etc/letsencrypt/dns-multi.ini << 'EOF'
dns_multi_provider = digitalocean
DO_AUTH_TOKEN = your_token_here
EOF
sudo chmod 600 /etc/letsencrypt/dns-multi.ini
```

**Hostinger**:
```bash
sudo tee /etc/letsencrypt/dns-multi.ini << 'EOF'
dns_multi_provider = hostinger
HOSTINGER_API_TOKEN = your_api_token_here
EOF
sudo chmod 600 /etc/letsencrypt/dns-multi.ini
```
Get API token: Hostinger hPanel → Advanced → API → Generate token (with DNS permissions)

**Namecheap**:
```bash
sudo tee /etc/letsencrypt/dns-multi.ini << 'EOF'
dns_multi_provider = namecheap
NAMECHEAP_API_USER = your_username
NAMECHEAP_API_KEY = your_api_key
EOF
sudo chmod 600 /etc/letsencrypt/dns-multi.ini
```

**Other providers:** https://go-acme.github.io/lego/dns/ (Vultr, DigitalOcean, Porkbun, GoDaddy, etc.)

## 3. Run the script

```bash
cd /home/ubuntu/gov-hub-dev
sudo bash setup-wildcard-cert-dns-multi.sh
```

## 4. Enable HTTPS for layer subdomains

```bash
sudo bash setup-layer-subdomain-ssl.sh
```
