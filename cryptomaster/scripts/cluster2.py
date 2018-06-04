from visualization_msgs.msg import Marker, MarkerArray
from std_msgs.msg import ColorRGBA
import rospy
from geometry_msgs.msg import Point, Vector3, Pose
from .util import point_distance
from .data import ClusterPoint
import states as states
import json
import numpy as np


class Clusterer():

    def __init__(self, cluster_topic, min_center_detections=15):
        self.centers = []
        self.markers = MarkerArray()
        self.centroid_treshold = 0.6
        self.min_center_distance = min_center_detections
        self.jobs = []
        self.jobs_created = 0
        self.state = states.DEFAULT
        self.jobs_calculated = False

        self.visualization_colors = [ColorRGBA(255, 0, 0, 1), ColorRGBA(
            255, 255, 0, 1), ColorRGBA(0, 0, 255, 1)]

        self.markers_pub = rospy.Publisher(
            'markers', MarkerArray, queue_size=1000)

        _ = rospy.Subscriber(cluster_topic, Marker, self.point_callback)

    def change_state(self,state):
        self.state = state

    def has_pending_jobs(self):
        return len(self.jobs) > 0

    def get_next_job(self):
        job = self.jobs[0]
        self.jobs = self.jobs[1:]
        return job

    def get_num_jobs(self):
        return len(self.jobs)

    def extract_color(self, color):
        if color.b < 50 and color.r > 100 and color.g > 100:
            return 'yellow'

        l = [color.b, color.r, color.g]

        max_ix = np.argmax(l)
        if max_ix == 0:
            return 'blue'
        elif max_ix == 1:
            return 'red'
        elif max_ix == 2:
            return 'green'
        else:
            print("ERROR!")




    def sort_jobs(self, gains):
        with_gains = [(job, gains.get(job.color)) for job in self.jobs]
        s = sorted(with_gains, key=lambda x: x[1], reverse=True)
        sorted_jobs = [job[0] for job in s]

        self.jobs = sorted_jobs
        self.jobs_calculated = True

    def reset_cluster(self, cluster_ix):
        cluster = self.centers[cluster_ix]
        reseted_cluster = ClusterPoint(cluster.x, cluster.y, 1, True)
        self.centers[cluster_ix] = reseted_cluster

    def find_nearest_cluster(self, p):
        closest_center = None
        min_dist = 999999999
        min_ix = 0


        for center_ix, center in enumerate(self.centers):
            dist = point_distance(p, center)
            if dist < min_dist:
                if closest_center:
                    print("Detected in multiple centers")

                closest_center = center
                min_dist = dist
                min_ix = center_ix

        return closest_center, min_ix

    def point_callback(self, marker):
        print(marker)
        p = marker.pose.position

        if self.state != states.OBSERVING:
            return

        closest_center, min_ix = self.find_nearest_cluster(p)
        color = marker.color
        discrete_color = self.extract_color(color)
        data = json.loads(marker.text) if marker.text else None

        if closest_center:
            print("[Cluster] updating existing cluster")
            new_center = closest_center.move_center(p, data)
            self.centers[min_ix] = new_center

            if new_center.n >= self.min_center_distance and not new_center.is_visited:
                new_center.is_visited = True
                self.centers[min_ix] = new_center
                self.jobs.append(new_center)
        else:
            self.centers.append(ClusterPoint(p.x, p.y, 1, color, discrete_color, data))
            print("[Cluster] Adding new center")

        self.publish_markers()

    def publish_markers(self):
        by_n = sorted(self.centers, key=lambda center: center.n, reverse=True)
        markers = [self.point_2_marker(p, ix)
                   for (ix, p) in enumerate(by_n[:3])]
        print("[Cluster] Publishing {} markers.".format(len(markers)))
        print(by_n)
        self.markers_pub.publish(markers)

    def point_2_marker(self, data_point, ix):
        pose = Pose()
        pose.position.x = data_point.x
        pose.position.y = data_point.y
        pose.position.z = 0.5
        marker = Marker()
        marker.header.stamp = rospy.Time(0)
        marker.header.frame_id = "map"
        marker.pose = pose
        marker.type = data_point.type
        marker.action = Marker.ADD
        marker.frame_locked = False
        marker.lifetime = rospy.Duration.from_sec(30)
        marker.id = ix
        marker.scale = Vector3(0.1, 0.1, 0.1)
        marker.color = data_point.color
        return marker