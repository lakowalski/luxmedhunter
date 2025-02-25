# Luxmed Hunter

## Installation
To set up the environment, run the following commands:
```sh
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
```

## Configuration
Create a `config.yaml` file with the following content:
```yaml
database_file: database.json
notifications:
  mail:
    enable: true # If you would like to get notifications after hunted appointment
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

## Database
The database is stored locally in the file specified in the config file, default is `database.json`.

## Commands

### Create Credentials
Generate credentials for your Luxmed account:
```sh
python cli.py create-credentials user@domain.com
```
You will be prompted to enter your password securely.

### Get Last Search
Retrieve the last search parameters from the Luxmed Patient Portal:
```sh
python cli.py get-last-search user@domain.com
```

### Create Appointment from Last Search
Schedule an appointment based on the latests search parameters:
```sh
python cli.py create-appointment-from-last-search user@domain.com
```

### Single On-Time Check
Perform a one-time check for available appointments:
```sh
python hunter.py
```

### Scheduled Checks
Run the task in 15-minute cycles:
```sh
python hunter.py --delay 900
```

### Background Execution
Run the task in the background and store the logs:
```sh
nohup python3 hunter.py --delay 900 >> logs.txt &
```