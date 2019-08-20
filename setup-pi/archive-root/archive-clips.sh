#!/bin/bash -eu

log "archive-clips: Moving clips to archive..."
SESSION_ID="$1"
NUM_FILES_MOVED=0

for file_name in "$ONE_MOUNT"/AnalizeThis/*; do
  [ -e "$file_name" ] || continue
  log "archive-clips: Moving $file_name ..."
  
  if mv -f -t "$ARCHIVE_MOUNT" -- "$file_name" >> "$LOG_FILE" 2>&1
  then
    log "archive-clips: Moved $file_name."

    /root/bin/main-server-status-notifier.sh "$SESSION_ID" "$$file_name" "$file_name"
    log "archive-clips: Main server is notified"

    NUM_FILES_MOVED=$((NUM_FILES_MOVED + 1))
  else
    log "archive-clips: Failed to move $file_name."
  fi
  
done
log "archive-clips: Moved $NUM_FILES_MOVED file(s)."

#finalize session from edge device
log "archive-clips: notifying main server that all files were transfered"
/root/bin/main-server-complete-notifier.sh "$SESSION_ID"

if [ $NUM_FILES_MOVED -gt 0 ]
then
/root/bin/send-pushover "$NUM_FILES_MOVED"
fi

log "archive-clips: Finished moving clips to archive."