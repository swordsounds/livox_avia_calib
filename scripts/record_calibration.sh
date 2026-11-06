#!/usr/bin/env bash
# Record already-running Avia and D435i drivers into a new MCAP bag directory.
set -eo pipefail

workspace_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
Usage: scripts/record_calibration.sh [OUTPUT_DIRECTORY] [--dry-run]

Start both sensor drivers first. Press Ctrl+C once to finish recording.
Default: bags/calibration_YYYYMMDD_HHMMSS_NANOSECONDS under this workspace.
An explicitly supplied output directory must not already exist.
--dry-run prints the command without checking publishers or starting recording.
EOF
  exit 0
fi

dry_run=false
output_dir=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=true ;;
    -*) echo "Unknown option: $arg" >&2; exit 2 ;;
    *)
      if [[ -n "$output_dir" ]]; then
        echo "Specify only one output directory." >&2
        exit 2
      fi
      output_dir="$arg"
      ;;
  esac
done
output_dir="${output_dir:-$workspace_dir/bags/calibration_$(date +%Y%m%d_%H%M%S_%N)}"

if [[ ! -f "$workspace_dir/install/setup.bash" ]]; then
  echo "Build the workspace with colcon build first." >&2
  exit 1
fi
source /opt/ros/humble/setup.bash
source "$workspace_dir/install/setup.bash"

topics=(
  /livox/lidar
  /livox/imu
  /camera/camera/color/image_raw
  /camera/camera/color/camera_info
  /camera/camera/depth/image_rect_raw
  /camera/camera/depth/camera_info
  /camera/camera/imu
  /tf
  /tf_static
)
record_command=(ros2 bag record --storage mcap --output "$output_dir"
  --qos-profile-overrides-path "$workspace_dir/config/recording_qos.yaml"
  "${topics[@]}")

if $dry_run; then
  printf '%q ' "${record_command[@]}"
  printf '\n'
  exit 0
fi

if [[ -e "$output_dir" ]]; then
  echo "Output already exists: $output_dir. Choose a new directory." >&2
  exit 1
fi
if ! ros2 bag list storage | rg -qx mcap; then
  echo "Install MCAP support: sudo apt-get install ros-humble-rosbag2-storage-mcap" >&2
  exit 1
fi

available_topics="$(ros2 topic list --no-daemon --spin-time 2)"
for required_topic in /livox/lidar /camera/camera/color/image_raw /camera/camera/color/camera_info; do
  if ! printf '%s\n' "$available_topics" | rg -Fxq "$required_topic"; then
    echo "Missing topic: $required_topic. Start both drivers (see README.md)." >&2
    exit 1
  fi
done

mkdir -p -- "$(dirname -- "$output_dir")"
echo "Recording to: $output_dir"
echo "Press Ctrl+C once and wait for the recorder to finish writing."
exec "${record_command[@]}"
