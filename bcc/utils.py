import json
from typing import List

from kafka import KafkaAdminClient
from kafka.admin import NewTopic, ConfigResource
from kafka.errors import TopicAlreadyExistsError

from bcc.Transaction import TransactionType


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, TransactionType):
            return obj.value
        return json.JSONEncoder.default(self, obj)


def initialize_broker(server: str, topics):
    """
    Initializes all topics needed by the application in the Kafka broker.

    Keyword parameters:
    - server -- IP address and port of the broker
    - topics -- List of all topics' info that need to be initialized
    """
    try:
        # Create all required topics (if they do not already exist)
        admin = KafkaAdminClient(bootstrap_servers=server)
        topics_list: List[NewTopic] = []
        for topic in topics:
            topics_list.append(
                NewTopic(
                    name=topic["name"],
                    num_partitions=topic["partitions"],
                    replication_factor=1,
                )
            )
        admin.create_topics(new_topics=topics_list, validate_only=False)
    # If topic(s) already exist, skip this error
    except TopicAlreadyExistsError:
        pass
    # Other exception occured - Forward the exception to the caller
    except Exception as e:
        raise e
    finally:
        # Change all topics' retention time
        altered_topics: List[ConfigResource] = []
        for topic in topics:
            altered_topics.append(
                ConfigResource(
                    resource_type="TOPIC",
                    name=topic["name"],
                    configs={"retention.ms": str(topic["retention"])},
                )
            )
        admin.alter_configs(config_resources=altered_topics)
