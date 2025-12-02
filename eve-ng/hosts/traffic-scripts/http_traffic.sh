#!/bin/sh
# HTTP Traffic Simulation Script
# Simulates web browsing between sites

# Target hosts
HOSTS="172.16.1.10 172.16.2.10 172.17.1.10 172.17.2.10 172.18.1.10 172.18.2.10"
HTTP_PORT=8080

MY_IP=$(ip -4 addr show eth0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')

echo "HTTP Traffic Simulator"
echo "======================"
echo "My IP: $MY_IP"

# Check if python3 is available for simple HTTP server
if command -v python3 > /dev/null 2>&1; then
    # Create a simple web page
    mkdir -p /var/www
    cat > /var/www/index.html << 'HTMLEOF'
<!DOCTYPE html>
<html>
<head><title>EUNIV Test Host</title></head>
<body>
<h1>EUNIV Network Test Host</h1>
<p>This is a test page for network traffic simulation.</p>
<p>Generated content for bandwidth testing:</p>
<pre>
HTMLEOF

    # Add some content to make it ~100KB
    for i in $(seq 1 1000); do
        echo "Line $i: Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua." >> /var/www/index.html
    done

    echo "</pre></body></html>" >> /var/www/index.html

    # Start simple HTTP server
    echo "Starting HTTP server on port $HTTP_PORT..."
    cd /var/www && python3 -m http.server $HTTP_PORT &
    sleep 2
fi

# Check if curl or wget is available
if command -v curl > /dev/null 2>&1; then
    FETCH_CMD="curl -s -o /dev/null -w '%{http_code}'"
elif command -v wget > /dev/null 2>&1; then
    FETCH_CMD="wget -q -O /dev/null"
else
    echo "No curl or wget available. Installing..."
    apk add --no-cache curl 2>/dev/null || apt-get install -y curl 2>/dev/null
    FETCH_CMD="curl -s -o /dev/null -w '%{http_code}'"
fi

# HTTP client traffic loop
while true; do
    echo "[$(date)] Starting HTTP requests..."

    for host in $HOSTS; do
        if [ "$host" != "$MY_IP" ]; then
            echo "  Fetching from $host:$HTTP_PORT..."

            # Make multiple requests to simulate browsing
            for i in 1 2 3 4 5; do
                curl -s -o /dev/null --connect-timeout 3 "http://$host:$HTTP_PORT/" 2>/dev/null &
                sleep 0.5
            done
        fi
    done

    # Wait before next round
    sleep 45

    echo "[$(date)] HTTP round complete."
done
