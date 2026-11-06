"""Start the Avia and D435i with the topics used by record_calibration.sh."""

from pathlib import Path

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, RegisterEventHandler
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessStart
from launch.events import matches_action
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode, Node
from launch_ros.event_handlers import OnStateTransition
from launch_ros.events.lifecycle import ChangeState
from launch_ros.parameter_descriptions import ParameterValue
from lifecycle_msgs.msg import Transition


def generate_launch_description():
    livox_share = Path(get_package_share_directory("livox_ros2_driver"))
    camera_share = Path(get_package_share_directory("realsense2_camera"))
    workspace = Path(__file__).resolve().parents[1]
    with (camera_share / "config" / "global_settings.yaml").open() as settings_file:
        lifecycle_enabled = yaml.safe_load(settings_file).get("use_lifecycle_node", False)

    arguments = [
        DeclareLaunchArgument("start_lidar", default_value="true"),
        DeclareLaunchArgument("start_camera", default_value="true"),
        DeclareLaunchArgument("rviz", default_value="false"),
        DeclareLaunchArgument(
            "lidar_config",
            default_value=str(livox_share / "config" / "livox_lidar_config.json"),
            description="Avia JSON configuration (absolute path).",
        ),
        DeclareLaunchArgument("publish_freq", default_value="10.0"),
        DeclareLaunchArgument("color_profile", default_value="640x480x30"),
        DeclareLaunchArgument("depth_profile", default_value="640x480x30"),
        DeclareLaunchArgument("camera_depth", default_value="true"),
        DeclareLaunchArgument("camera_imu", default_value="true"),
        DeclareLaunchArgument("camera_pointcloud", default_value="false"),
    ]

    lidar = Node(
        package="livox_ros2_driver",
        executable="livox_ros2_driver_node",
        name="livox_lidar_publisher",
        output="screen",
        condition=IfCondition(LaunchConfiguration("start_lidar")),
        parameters=[{
            "xfer_format": 0,  # PointCloud2 for ros2_calib.
            "multi_topic": 0,
            "data_src": 0,  # Direct LiDAR, including Converter 2.0.
            "publish_freq": ParameterValue(LaunchConfiguration("publish_freq"), value_type=float),
            "output_data_type": 0,
            "frame_id": "livox_frame",
            "user_config_path": ParameterValue(LaunchConfiguration("lidar_config"), value_type=str),
            "cmdline_input_bd_code": "",  # Use the JSON configuration.
        }],
    )

    camera_action = LifecycleNode if lifecycle_enabled else Node
    camera = camera_action(
        package="realsense2_camera",
        executable="realsense2_camera_node",
        namespace="camera",
        name="camera",
        output="screen",
        condition=IfCondition(LaunchConfiguration("start_camera")),
        parameters=[{
            "enable_color": True,
            "enable_depth": ParameterValue(LaunchConfiguration("camera_depth"), value_type=bool),
            "rgb_camera.color_profile": ParameterValue(LaunchConfiguration("color_profile"), value_type=str),
            "depth_module.depth_profile": ParameterValue(LaunchConfiguration("depth_profile"), value_type=str),
            "enable_gyro": ParameterValue(LaunchConfiguration("camera_imu"), value_type=bool),
            "enable_accel": ParameterValue(LaunchConfiguration("camera_imu"), value_type=bool),
            "unite_imu_method": 2,
            "pointcloud.enable": ParameterValue(LaunchConfiguration("camera_pointcloud"), value_type=bool),
        }],
    )

    lifecycle_handlers = []
    if lifecycle_enabled:
        lifecycle_handlers = [
            RegisterEventHandler(OnProcessStart(
                target_action=camera,
                on_start=[EmitEvent(event=ChangeState(
                    lifecycle_node_matcher=matches_action(camera),
                    transition_id=Transition.TRANSITION_CONFIGURE,
                ))],
            )),
            RegisterEventHandler(OnStateTransition(
                target_lifecycle_node=camera,
                start_state="configuring",
                goal_state="inactive",
                entities=[EmitEvent(event=ChangeState(
                    lifecycle_node_matcher=matches_action(camera),
                    transition_id=Transition.TRANSITION_ACTIVATE,
                ))],
            )),
        ]

    rviz = Node(
        package="rviz2",
        executable="rviz2",
        output="screen",
        condition=IfCondition(LaunchConfiguration("rviz")),
        arguments=["-d", str(workspace / "config" / "calibration.rviz")],
    )

    # Register lifecycle handlers before starting the camera process.
    return LaunchDescription(arguments + lifecycle_handlers + [lidar, camera, rviz])
