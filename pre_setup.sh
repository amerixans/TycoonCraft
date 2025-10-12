# 0) Base prep
apt update && apt -y upgrade
apt install -y git curl
mkdir -p /var/www

# 1) Get the repo that contains setup.sh (adjust branch if needed)
cd /root
git clone -b feature/big-refactor --single-branch --depth 1 https://github.com/amerixans/tycooncraft.git
cd tycooncraft    # if setup.sh is in a subfolder, cd there

# 2) (Optional) pre-seed secrets so you won't be prompted
# export OPENAI_API_KEY='sk-...'
# export DJANGO_SUPERUSER_PASSWORD='your-strong-password'

# 3) Run the installer
chmod +x setup.sh
sudo -E ./setup.sh

# 4) Quick health checks after it completes
systemctl status tycooncraft --no-pager
curl -I http://127.0.0.1:8000/api/game-state/
curl -I -H "Host: tycooncraft.com" http://127.0.0.1/