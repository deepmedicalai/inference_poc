#!/bin/bash

SESSION_ID="$1"
# export MAIN_SERVER_URL="http://localhost:5000"
# export MAIN_SERVER_APIKEY="edge0001-key"

if [ -r "/root/.deepMedicalAIMainServerCredentials"  ]
then
    log "main-server-complete-notifier: Sending status update to main server."

    source /root/.deepMedicalAIMainServerCredentials

    content=$(curl -L -w "\\n%{http_code}" -s -X POST --header "X-Api-Key:$MAIN_SERVER_APIKEY" --header "Content-Type:application/json" "$MAIN_SERVER_URL/edge/statusupdatecompleted/$SESSION_ID")
    STATUS=$(echo $content | tail -c 4)
    if [ "$STATUS" = "200" ]
    then
        body=${content%\}*}} 
        is_ack=$(echo $body | jq '.status')
        if [ "$is_ack" = "ack" ]
        then
            log "main-server-complete-notifier: code 'ack'"
            echo "ack"
        else
            log "main-server-complete-notifier: main server has returned an unexpected result. Details"
            log "$content"
            echo "error"
        fi
    else
        log "main-server-complete-notifier: main server has returned an unexpected result. Details"
        log "$content"
        echo "error"
    fi
fi

