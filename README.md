# Avia and D435i calibration workspace

## Build

```bash
git submodule update --init --recursive
source /opt/ros/humble/setup.bash
colcon build
source install/setup.bash
```

## Record LiDAR and camera data

Install the MCAP storage plugin once:

```bash
sudo apt-get install ros-humble-rosbag2-storage-mcap
```

Run these commands from the workspace root. In each sensor terminal, first run
`source install/setup.bash`.

Terminal 1 — start both sensors:

```bash
ros2 launch launch/avia_d435i.launch.py
```

This publishes Avia `PointCloud2`, D435i RGB/depth images and camera info, and
both IMUs. It automatically configures and activates the camera if the driver
was built in lifecycle mode. Stop any existing sensor drivers first to avoid
opening the same device twice. Press Ctrl+C to stop both sensors.

To also show the Avia cloud and camera image in RViz:

```bash
ros2 launch launch/avia_d435i.launch.py rviz:=true
```

Optional settings include `color_profile:=640x480x15`,
`depth_profile:=640x480x15`, `camera_depth:=false`, `camera_imu:=false`, `camera_pointcloud:=true`,
`publish_freq:=10.0`, and `lidar_config:=/absolute/path/to/config.json`.
Use `start_camera:=false` or `start_lidar:=false` when that sensor is already
running separately. List all arguments with:

```bash
ros2 launch launch/avia_d435i.launch.py --show-args
```

For a USB 2 connection, try RGB alone at 15 FPS to reduce bandwidth:

```bash
ros2 launch launch/avia_d435i.launch.py rviz:=true \
  color_profile:=640x480x15 camera_depth:=false camera_imu:=false
```

Depth and camera IMU are optional for LiDAR-to-RGB extrinsic calibration. The
recorder still captures RGB, camera info, LiDAR, and transforms in this mode.
Use the camera intrinsics for the selected image resolution. This mode reduces
USB traffic but does not guarantee that a particular USB connection will stream
reliably; check that images actually arrive before recording.

Terminal 2 — record into a timestamped directory under `bags/`:

```bash
./scripts/record_calibration.sh
```

Or choose a new output directory (relative to your current directory, or absolute):

```bash
./scripts/record_calibration.sh bags/target_position_01
```

Press **Ctrl+C once** and wait for recording to finish. The output contains
`metadata.yaml` and an `.mcap` file. Open the `.mcap` file in `ros2_calib`.
Existing output directories are never overwritten. Recordings are excluded from Git.

The script records:

| Data | Topics |
| --- | --- |
| Avia cloud and IMU | `/livox/lidar`, `/livox/imu` |
| RGB image and intrinsics | `/camera/camera/color/image_raw`, `/camera/camera/color/camera_info` |
| Depth image and intrinsics | `/camera/camera/depth/image_rect_raw`, `/camera/camera/depth/camera_info` |
| Combined camera IMU | `/camera/camera/imu` |
| Transforms | `/tf`, `/tf_static` |

Required topics are checked before recording; optional topics are recorded when
available. Topic discovery alone does not verify that frames are arriving.
Use a USB 3 cable/port for the D435i and check the recording afterward:

```bash
ros2 bag info bags/target_position_01
```

Confirm nonzero counts for the cloud, RGB image, and camera info. For
`ros2_calib`, select those three topics. Recording preserves the drivers'
timestamps; it does not synchronize the devices or generate the unknown
LiDAR-to-camera transform. Keep the rig and scene still for static extrinsic
calibration captures, with useful features visible to both sensors.

Preview the recording command without starting a recording:

```bash
./scripts/record_calibration.sh --dry-run
```

## View an exported calibration in RViz

On ros2_calib's image/point-cloud screen, use **Export Calibration** and save to
`calibration/avia_to_d435i.yaml`. It must contain `translation: {x, y, z}` in
metres and `rotation: {x, y, z, w}` as a quaternion. **View TF/URDF Export**
opens a separate screen for frame conversion and text/URDF export; that text is
not the YAML format used by this launcher. The result preview includes the
calibrated sensor link even when it was absent from the original bag's TF tree.
Older app versions could save an error string from this screen; such files
must be re-exported using the direct YAML button.

With both sensors already running:

```bash
source install/setup.bash
ros2 launch launch/view_calibration.launch.py
```

Or start both sensors and RViz together (RGB-only at 640x480x15 for USB 2):

```bash
ros2 launch launch/view_calibration.launch.py start_sensors:=true
```

The **LiDAR on RGB** camera panel projects the Avia cloud onto the image using
the matching CameraInfo topic. The main 3D view shows the cloud and sensor TF
frames. Inspect physical object boundaries at different distances, especially
features not used for calibration. A screenshot alone is not an accuracy metric.

The exported `T_camera_lidar` maps LiDAR points into camera optical coordinates.
It is published directly with parent `camera_color_optical_frame` and child
`livox_frame`, joining the existing RealSense tree without assigning the camera
optical frame a second parent. Stop any other publisher of this calibrated TF.
To use another export, pass `calibration_file:=/absolute/path/to/file.yaml`.
Restart this launch after changing the calibration file.

For offline validation, stop the live sensors, launch with
`use_sim_time:=true`, then play a separate recording in another sourced terminal:

```bash
ros2 launch launch/view_calibration.launch.py use_sim_time:=true
# In another terminal:
ros2 bag play bags/calibration_01 --clock --loop
```

The camera's internal transforms come from the live driver or the bag's
`/tf_static`. No transform is inferred or substituted when the export is invalid.
