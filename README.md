# Luxmed Snip

## Install
```
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
```

## Make a config file
Create a `config.yaml` file.
```yaml
database_file: database.json
notifications:
  mail:
    enable: true
    recipients: user@gmail.com
    provider: SES
    ses:
      sender: sender@domain.com
      session:
        aws_access_key_id: "AKIAXXXXXXXXXXXXXXXX"
        aws_secret_access_key: "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"
        region_name: "eu-west-1"
    mailgun:
      domain: sandbox1234567890abcdefgh.mailgun.org
      apikey: abcdef0123456789012-12345678-12345678
    smtp:
      smtp_server: smtp.server.com
      smtp_port: 567
      email: username@server.com
      password: password
```

# Launch
On-time check.
```
hunter.py
```

Make a task executed in 15 minutes cycles.
```
hunter.py --delay 900
```

Put it to the background and store the logs.
```
nohup python3 hunter.py --delay 900 >> logs.txt &
```