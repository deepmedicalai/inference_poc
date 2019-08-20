#!/bin/bash -eu

function ensure_archive_is_mounted () {
  log "Ensuring deep medical ai archive is mounted..."
  ensure_mountpoint_is_mounted_with_retry "$ARCHIVE_MOUNT"
  log "Ensured deep medical ai archive is mounted."
}

ensure_archive_is_mounted