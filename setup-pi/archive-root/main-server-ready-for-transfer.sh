#!/bin/bash

# function log() {
#     echo ""
# }

# export MAIN_SERVER="http://localhost:5000"
# export MAIN_SERVER_AUTH_KEY="edge0001-key"

#if [ "$MAIN_SERVER" = "$MAIN_SERVER" ]
if [ -r "/root/.deepMedicalAIMainServerCredentials"  ]
then
    log "main-server-ready-for-transfer: Checking if main server initialized new transfer request."

    source /root/.deepMedicalAIMainServerCredentials

    content=$(curl -L -w "%{http_code}" -s -X GET --header "X-Api-Key:$MAIN_SERVER_APIKEY" --header "Content-Type:application/json" "$MAIN_SERVER_URL/edge/readyfortransfer")
    
    STATUS=$(echo $content | tail -c 4)
    if [ "$STATUS" = "200" ]
    then
        body=${content%\}*}} 
        is_ready=$(echo $body | jq '.ready')
        if [ "$is_ready" = "true" ]
        then
            session_id=$(echo $body | jq '.session_id')
            log "main-server-ready-for-transfer: new session $session_id"
            echo $session_id
        else
            log "main-server-ready-for-transfer: not ready"
            echo "not_ready"
        fi
    else    
        log "main-server-ready-for-transfer: main server has returned an error. Details"
        log "$content"
        echo "error"
    fi
fi


