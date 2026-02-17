# =============================================================================
# MikroTik QoS Configuration (Queue Trees)
# Generated from topology v4.0.0
# DO NOT EDIT MANUALLY - Regenerate with: python3 scripts/generate-terraform-mikrotik.py
# =============================================================================

# -----------------------------------------------------------------------------
# Queue Type Definitions
# -----------------------------------------------------------------------------

resource "routeros_queue_type" "pcq_download" {
  name     = "pcq-download"
  kind     = "pcq"
  pcq_rate = "0"
  pcq_classifier = ["dst-address"]
}

resource "routeros_queue_type" "pcq_upload" {
  name     = "pcq-upload"
  kind     = "pcq"
  pcq_rate = "0"
  pcq_classifier = ["src-address"]
}

# -----------------------------------------------------------------------------
# Simple Queues (Per-Network Limits)
# -----------------------------------------------------------------------------

resource "routeros_queue_simple" "limit_net_iot" {
  name       = "limit-net-iot"
  target     = ["192.168.40.0/24"]
  max_limit  = "5M/10M"
  comment    = "IoT devices limited bandwidth"
}

resource "routeros_queue_simple" "limit_net_guest" {
  name       = "limit-net-guest"
  target     = ["192.168.30.0/24"]
  max_limit  = "10M/20M"
  queue      = "pcq-upload-default/pcq-download-default"
  comment    = "Guest network per-device limit"
}

# -----------------------------------------------------------------------------
# Queue Tree (Traffic Prioritization)
# -----------------------------------------------------------------------------

# Parent queue on WAN interface
resource "routeros_queue_tree" "download_parent" {
  name       = "Download"
  parent     = "global"
  max_limit  = "100M"
  comment    = "Download traffic shaping"
}

resource "routeros_queue_tree" "upload_parent" {
  name       = "Upload"
  parent     = "global"
  max_limit  = "20M"
  comment    = "Upload traffic shaping"
}

# VoIP & Video Calls
resource "routeros_queue_tree" "qos_voip_down" {
  name       = "VoIP & Video Calls-Down"
  parent     = routeros_queue_tree.download_parent.name
  priority   = 1
  limit_at   = "10M"
  max_limit  = "30M"
  burst_limit = "50M"
  burst_time  = "2s"
  burst_threshold = "10M"
  packet_mark = ["qos-voip"]
  comment    = "Real-time voice and video"

  depends_on = [routeros_queue_tree.download_parent]
}

resource "routeros_queue_tree" "qos_voip_up" {
  name       = "VoIP & Video Calls-Up"
  parent     = routeros_queue_tree.upload_parent.name
  priority   = 1
  limit_at   = "2M"
  max_limit  = "6M"
  burst_limit = "10M"
  burst_time  = "2s"
  burst_threshold = "2M"
  packet_mark = ["qos-voip"]
  comment    = "Real-time voice and video"

  depends_on = [routeros_queue_tree.upload_parent]
}

# Gaming
resource "routeros_queue_tree" "qos_gaming_down" {
  name       = "Gaming-Down"
  parent     = routeros_queue_tree.download_parent.name
  priority   = 2
  limit_at   = "15M"
  max_limit  = "40M"
  burst_limit = "60M"
  burst_time  = "1s"
  burst_threshold = "15M"
  packet_mark = ["qos-gaming"]
  comment    = "Low-latency gaming traffic"

  depends_on = [routeros_queue_tree.download_parent]
}

resource "routeros_queue_tree" "qos_gaming_up" {
  name       = "Gaming-Up"
  parent     = routeros_queue_tree.upload_parent.name
  priority   = 2
  limit_at   = "3M"
  max_limit  = "8M"
  burst_limit = "12M"
  burst_time  = "1s"
  burst_threshold = "3M"
  packet_mark = ["qos-gaming"]
  comment    = "Low-latency gaming traffic"

  depends_on = [routeros_queue_tree.upload_parent]
}

# Interactive
resource "routeros_queue_tree" "qos_interactive_down" {
  name       = "Interactive-Down"
  parent     = routeros_queue_tree.download_parent.name
  priority   = 3
  limit_at   = "20M"
  max_limit  = "60M"
  packet_mark = ["qos-interactive"]
  comment    = "SSH, RDP, remote access"

  depends_on = [routeros_queue_tree.download_parent]
}

resource "routeros_queue_tree" "qos_interactive_up" {
  name       = "Interactive-Up"
  parent     = routeros_queue_tree.upload_parent.name
  priority   = 3
  limit_at   = "4M"
  max_limit  = "12M"
  packet_mark = ["qos-interactive"]
  comment    = "SSH, RDP, remote access"

  depends_on = [routeros_queue_tree.upload_parent]
}

# Streaming
resource "routeros_queue_tree" "qos_streaming_down" {
  name       = "Streaming-Down"
  parent     = routeros_queue_tree.download_parent.name
  priority   = 4
  limit_at   = "20M"
  max_limit  = "80M"
  packet_mark = ["qos-streaming"]
  comment    = "Video streaming services"

  depends_on = [routeros_queue_tree.download_parent]
}

resource "routeros_queue_tree" "qos_streaming_up" {
  name       = "Streaming-Up"
  parent     = routeros_queue_tree.upload_parent.name
  priority   = 4
  limit_at   = "4M"
  max_limit  = "16M"
  packet_mark = ["qos-streaming"]
  comment    = "Video streaming services"

  depends_on = [routeros_queue_tree.upload_parent]
}

# Web Browsing
resource "routeros_queue_tree" "qos_web_down" {
  name       = "Web Browsing-Down"
  parent     = routeros_queue_tree.download_parent.name
  priority   = 5
  limit_at   = "15M"
  max_limit  = "70M"
  packet_mark = ["qos-web"]
  comment    = "General web traffic"

  depends_on = [routeros_queue_tree.download_parent]
}

resource "routeros_queue_tree" "qos_web_up" {
  name       = "Web Browsing-Up"
  parent     = routeros_queue_tree.upload_parent.name
  priority   = 5
  limit_at   = "3M"
  max_limit  = "14M"
  packet_mark = ["qos-web"]
  comment    = "General web traffic"

  depends_on = [routeros_queue_tree.upload_parent]
}

# Bulk Transfer
resource "routeros_queue_tree" "qos_bulk_down" {
  name       = "Bulk Transfer-Down"
  parent     = routeros_queue_tree.download_parent.name
  priority   = 6
  limit_at   = "10M"
  max_limit  = "90M"
  packet_mark = ["qos-bulk"]
  comment    = "File transfers, backups"

  depends_on = [routeros_queue_tree.download_parent]
}

resource "routeros_queue_tree" "qos_bulk_up" {
  name       = "Bulk Transfer-Up"
  parent     = routeros_queue_tree.upload_parent.name
  priority   = 6
  limit_at   = "2M"
  max_limit  = "18M"
  packet_mark = ["qos-bulk"]
  comment    = "File transfers, backups"

  depends_on = [routeros_queue_tree.upload_parent]
}

# Downloads & P2P
resource "routeros_queue_tree" "qos_downloads_down" {
  name       = "Downloads & P2P-Down"
  parent     = routeros_queue_tree.download_parent.name
  priority   = 8
  limit_at   = "5M"
  max_limit  = "95M"
  packet_mark = ["qos-downloads"]
  comment    = "Low priority bulk downloads"

  depends_on = [routeros_queue_tree.download_parent]
}

resource "routeros_queue_tree" "qos_downloads_up" {
  name       = "Downloads & P2P-Up"
  parent     = routeros_queue_tree.upload_parent.name
  priority   = 8
  limit_at   = "1M"
  max_limit  = "19M"
  packet_mark = ["qos-downloads"]
  comment    = "Low priority bulk downloads"

  depends_on = [routeros_queue_tree.upload_parent]
}

# -----------------------------------------------------------------------------
# Mangle Rules for Traffic Marking
# -----------------------------------------------------------------------------

resource "routeros_ip_firewall_mangle" "mark_qos_voip" {
  chain       = "forward"
  action      = "mark-packet"
  new_packet_mark = "qos-voip"
  passthrough = true
  protocol    = "tcp"
  dst_port    = "5060,5061,10000-20000"
  comment     = "Mark VoIP & Video Calls traffic"
}

resource "routeros_ip_firewall_mangle" "mark_qos_gaming" {
  chain       = "forward"
  action      = "mark-packet"
  new_packet_mark = "qos-gaming"
  passthrough = true
  protocol    = "tcp"
  dst_port    = "3074,3478-3480,27015-27030"
  comment     = "Mark Gaming traffic"
}

resource "routeros_ip_firewall_mangle" "mark_qos_interactive" {
  chain       = "forward"
  action      = "mark-packet"
  new_packet_mark = "qos-interactive"
  passthrough = true
  protocol    = "tcp"
  dst_port    = "22,3389,5900"
  comment     = "Mark Interactive traffic"
}


resource "routeros_ip_firewall_mangle" "mark_qos_web" {
  chain       = "forward"
  action      = "mark-packet"
  new_packet_mark = "qos-web"
  passthrough = true
  protocol    = "tcp"
  dst_port    = "80,443"
  comment     = "Mark Web Browsing traffic"
}

resource "routeros_ip_firewall_mangle" "mark_qos_bulk" {
  chain       = "forward"
  action      = "mark-packet"
  new_packet_mark = "qos-bulk"
  passthrough = true
  protocol    = "tcp"
  dst_port    = "21,22,873"
  comment     = "Mark Bulk Transfer traffic"
}


