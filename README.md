# MLN App
Major League Numberball API

www.majorleagueguessball.com/api/v1/ui/

**Table of Contents**

 - [Key Features](#key-features)
 - [Installation](#installation)
 - [Configuration](#configuration)
 - [Launching Site](#launching-site)

## Key Features

 - Minimal Flask backend
 - Refreshes from MLN Sheets data repository regularly
 - Data stored in SQLite3 database and made available via Swagger/OpenAPI

## Installation
```
sudo apt-get -y install python3.8 python3.8-venv python3.8-dev supervisor nginx git
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.6 1
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.8 2
git clone https://github.com/dyslexda/MLN_API.git
cd MLN_API
python3 -m venv mln-env
source mln-env/bin/activate
pip3 install -r requirements.txt
```

## Configuration
The .env file must be configured for a local branch. Add it manually to /MLN_API.
```
FLASK_APP=app.py
FLASK_ENV=development #Change to "production" when not in private test env
SESSION_COOKIE_SECURE=False #Change to "True" if running with HTTPS
SECRET_KEY='' #Random string of letters and numbers
LESS_BIN=/usr/local/bin/lessc
ASSETS_DEBUG=False
LESS_RUN_IN_DEBUG=False
COMPRESSOR_DEBUG=True
P_MASTER_LOG = '' #Sheets ID with formatted data for shared/sheets_refresh.py
```

## Launching Site


Development:
 - Directly launch from Python file for easy debugging, accessible on your server's IP: ```python3 flask_app/wsgi.py```

Production:
Create a supervisorctl file using the following format:
```
[group:baseball]
programs=flask,sheets_ref

[program:flask]
command=/home/[user]/MLN_API/mln-env/bin/gunicorn -b localhost:8000 -w 4 flask_app.wsgi:app
directory=/home/[user]/MLN_API
user=[user]
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true

[program:sheets_ref]
command=/home/[user]/MLN_API/mln-env/bin/python3 shared/sheets_refresh.py
directory=/home/[user]/MLN_API
user=[user]
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
```

Create an nginx configuration file in /etc/nginx/sites-available and link to sites-enabled:

```
server {
    # listen on port 80 (http)
    listen 80;
    server_name majorleagueguessball.com;
    location ~ /.well-known {
        root /home/[user]/MLN_API/flask_app/auth/certs;
    }
    location / {
        # redirect any requests to the same URL but on https
        return 301 https://$host$request_uri;
    }

}
server {
    # listen on port 443 (https)
    listen 443 ssl;
    server_name _;
    # location of the self-signed SSL certificate
    ssl_certificate /etc/letsencrypt/live/majorleagueguessball.com/fullchain.pem; # managed by Certbot
    ssl_certificate_key /etc/letsencrypt/live/majorleagueguessball.com/privkey.pem; # managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot
    # write access and error logs to /var/log
    access_log /var/log/baseball_access.log;
    error_log /var/log/baseball_error.log;
    location / {
        # forward application requests to the gunicorn server
        proxy_pass http://localhost:8000;
        proxy_redirect off;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Launch with "sudo supervisorctl reload".
