"""Publish a ros2_calib T_camera_lidar export and inspect it in RViz."""

import math
from pathlib import Path

import yaml
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def calibration_transform(path):
    """Read metres and an xyzw quaternion mapping LiDAR points into the camera."""
    try:
        with Path(path).open() as stream:
            data = yaml.safe_load(stream)
        translation = [float(data["translation"][axis]) for axis in "xyz"]
        quaternion = [float(data["rotation"][axis]) for axis in "xyzw"]
        if not all(math.isfinite(value) for value in translation + quaternion):
            raise ValueError("Non-finite transform value")
        norm = math.sqrt(sum(value * value for value in quaternion))
        if abs(norm - 1.0) > 0.01:
            raise ValueError("Rotation quaternion must have unit length")
        return translation, [value / norm for value in quaternion]
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as error:
        raise RuntimeError(
            f"Invalid calibration file {path}: {error}. Export it using the "
            "'Export Calibration' button on ros2_calib's image/point-cloud screen, "
            "not 'Export Target Transform' on the TF-chain screen."
        ) from error


def publish_calibration(context):
    translation, quaternion = calibration_transform(
        LaunchConfiguration("calibration_file").perform(context)
    )
    # TF stores the child's pose in its parent. T_camera_lidar therefore has
    # the camera optical frame as parent and the LiDAR frame as child.
    return [Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="avia_d435i_calibration_tf",
        output="screen",
        arguments=[
            "--x", str(translation[0]), "--y", str(translation[1]),
            "--z", str(translation[2]), "--qx", str(quaternion[0]),
            "--qy", str(quaternion[1]), "--qz", str(quaternion[2]),
            "--qw", str(quaternion[3]),
            "--frame-id", "camera_color_optical_frame",
            "--child-frame-id", "livox_frame",
        ],
    )]


def generate_launch_description():
    workspace = Path(__file__).resolve().parents[1]
    return LaunchDescription([
        DeclareLaunchArgument(
            "calibration_file",
            default_value=str(workspace / "calibration" / "avia_to_d435i.yaml"),
        ),
        DeclareLaunchArgument(
            "start_sensors", default_value="false",
            description="Start both sensors; leave false if already running or playing a bag.",
        ),
        DeclareLaunchArgument("rviz", default_value="true"),
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        # Validate the export before starting sensors or opening RViz.
        OpaqueFunction(function=publish_calibration),
        GroupAction(
            condition=IfCondition(LaunchConfiguration("start_sensors")),
            actions=[IncludeLaunchDescription(
                PythonLaunchDescriptionSource(str(workspace / "launch" / "avia_d435i.launch.py")),
                launch_arguments={
                    "start_lidar": "true",
                    "start_camera": "true",
                    "rviz": "false",
                    "color_profile": "640x480x15",
                    "camera_depth": "false",
                    "camera_imu": "false",
                }.items(),
            )],
        ),
        Node(
            package="rviz2", executable="rviz2", output="screen",
            condition=IfCondition(LaunchConfiguration("rviz")),
            arguments=["-d", str(workspace / "config" / "validation.rviz")],
            parameters=[{
                "use_sim_time": ParameterValue(LaunchConfiguration("use_sim_time"), value_type=bool),
            }],
        ),
    ])
