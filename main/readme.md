

## DEBUG Python in VS Code

### create virtual environment
Running in ./main
```
python3 -m venv env
```

If you don't see your `Python Interpreter`, then follow this link: https://code.visualstudio.com/docs/python/environments
Eventually, I had created the following entry in `./.vscode/settings.json`
```
{
    "python.pythonPath": "./main/env/bin/python3"
}
```


## start Integrated Terminal

Open "Create: New Integrated Terminal"  it opens Python environment, which should be pointing to environment you have created


## install prerequisites

while in `/main` directory, install both requirements
```
cd ./main
pip install -r ./web-requirements.txt -r ./worker-requirements.txt 
```

## test the app

Test that flask is running
```

export FLASK_APP=webserver
export FLASK_RUN_HOST="0.0.0.0"
export APP_SETTINGS="settings.config.DevelopmentConfig"
flask run
```

## Attach debugger

Make sure you stop app that was running in the previous step: `Ctrl + C`

Create new Debug configuration:
```
{
    // Use IntelliSense to learn about possible attributes.
    // Hover to view descriptions of existing attributes.
    // For more information, visit: https://go.microsoft.com/fwlink/?linkid=830387
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Flask",
            "type": "python",
            "request": "launch",
            "module": "flask",
            "cwd": "${workspaceFolder}/main-tmp/webserver",
            "env": {
                "FLASK_APP": "app.py",
                "FLASK_ENV": "development",
                "FLASK_DEBUG": "0"
            },
            "args": [
                "run",
                "--no-debugger",
                "--no-reload"
            ],
            "jinja": true
        }
    ]
}
```


# Linux Stuff
get jq

```
brew install jq
```

for linus/Raspberry
```
sudo apt-get install jq
```


### Ready for new transfer
```
export MAIN_SERVER="http://localhost:5000"
export MAIN_SERVER_AUTH_KEY="edge0001-key"

```


Example of linux post message




```
export SESSION_ID="54663"
export FILE_NAME="DCM0002.dcm"
export FILE_PATH="/subfolder/DCM0002.dcm"
export MAIN_SERVER="http://localhost:5000"
export MAIN_SERVER_AUTH_KEY="edge0001-key"

content=$(curl -L -w "%{http_code}" -s -X POST --header "Authorization:key=$MAIN_SERVER_AUTH_KEY" --header "Content-Type:application/json" "$MAIN_SERVER/edge/statusupdate/$SESSION_ID" -d '{"file_name": "$FILE_NAME", "file_path": "$FILE_PATH"}')
STATUS=$(echo $content | tail -c 4)

echo "status: $STATUS"
echo ${content%\}*}} | jq '.status'

```