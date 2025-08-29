#!/usr/bin/env python3
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import Lambda, ECS
from diagrams.aws.storage import S3
from diagrams.aws.database import Dynamodb, ElastiCache
from diagrams.aws.network import APIGateway, CloudFront, ALB
from diagrams.aws.security import Cognito, IAM, IAMAWSSts
from diagrams.aws.devtools import XRay
from diagrams.aws.integration import SNS, SQS, Eventbridge
from diagrams.aws.ml import Sagemaker
from diagrams.aws.management import Cloudwatch
from diagrams.custom import Custom
from diagrams.onprem.client import Users
from diagrams.generic.device import Mobile

# Create the AWS architecture diagram for ilikeyacut
with Diagram("ilikeyacut AWS Infrastructure", filename="aws_infrastructure_diagram", direction="TB", show=False, graph_attr={"dpi": "300", "size": "20,16!", "ratio": "fill"}):
    
    # External users and services
    users = Users("iOS App Users")
    mobile = Mobile("ilikeyacut iOS App")
    
    # CDN and Load Balancing
    with Cluster("Content Delivery"):
        cdn = CloudFront("CloudFront CDN\nGlobal Distribution")
        alb = ALB("Application\nLoad Balancer")
    
    # API Layer
    with Cluster("API Gateway"):
        api = APIGateway("REST API\nEndpoints")
        
    # Authentication & Authorization
    with Cluster("Authentication"):
        cognito_pool = Cognito("User Pool\nEmail/Social Auth")
        cognito_identity = Cognito("Identity Pool\nFederated Access")
        iam = IAM("IAM Roles\n& Policies")
        sts = IAMAWSSts("STS\nTemp Credentials")
    
    # Compute Layer - Lambda Functions
    with Cluster("Serverless Compute"):
        with Cluster("Core Functions"):
            auth_lambda = Lambda("Auth Service\nLogin/Signup")
            upload_lambda = Lambda("Upload Service\nImage Processing")
            ai_lambda = Lambda("AI Proxy\nGemini Integration")
            
        with Cluster("Business Logic"):
            user_lambda = Lambda("User Management\nProfile/Settings")
            gallery_lambda = Lambda("Gallery Service\nTemplates/History")
            notification_lambda = Lambda("Notification\nPush/Email")
    
    # Storage Layer
    with Cluster("Storage"):
        with Cluster("S3 Buckets"):
            template_bucket = S3("Hairstyle Templates\n50+ Presets")
            user_bucket = S3("User Images\nOriginal/Edited")
            static_bucket = S3("Static Assets\nIcons/Resources")
            
        with Cluster("Database"):
            user_table = Dynamodb("Users Table\nProfiles")
            session_table = Dynamodb("Sessions Table\nEdit History")
            gallery_table = Dynamodb("Gallery Table\nMetadata")
    
    # AI/ML Services
    with Cluster("AI Processing"):
        sagemaker = Sagemaker("SageMaker\nEndpoint")
        # Note: Google Gemini is external, represented as custom
    
    # Event Processing
    with Cluster("Event System"):
        eventbridge = Eventbridge("EventBridge\nScheduler")
        with Cluster("Queues"):
            sqs_fifo = SQS("FIFO Queue\nOrder Processing")
            sqs_standard = SQS("Standard Queue\nAsync Tasks")
        sns_topic = SNS("SNS Topics\nNotifications")
    
    # Monitoring & Caching
    with Cluster("Operations"):
        with Cluster("Monitoring"):
            cloudwatch = Cloudwatch("CloudWatch\nLogs & Metrics")
            xray = XRay("X-Ray\nTracing")
            alarms = Cloudwatch("Alarms\nError Alerts")
            
        with Cluster("Caching"):
            redis = ElastiCache("Redis Cache\nSession Store")
    
    # Define connections with labels
    users >> Edge(label="HTTPS") >> mobile
    mobile >> Edge(label="API Calls") >> cdn
    cdn >> alb
    alb >> api
    
    # Authentication flow
    api >> Edge(label="Auth") >> auth_lambda
    auth_lambda >> cognito_pool
    cognito_pool >> cognito_identity
    cognito_identity >> sts
    sts >> Edge(label="Temp Creds") >> iam
    
    # Image upload flow
    api >> Edge(label="Upload") >> upload_lambda
    upload_lambda >> user_bucket
    upload_lambda >> Edge(label="Process") >> ai_lambda
    
    # AI processing
    ai_lambda >> Edge(label="Inference") >> sagemaker
    ai_lambda >> Edge(label="Queue", style="dashed") >> sqs_standard
    
    # User management
    api >> Edge(label="User Ops") >> user_lambda
    user_lambda >> user_table
    user_lambda >> redis
    
    # Gallery operations
    api >> Edge(label="Gallery") >> gallery_lambda
    gallery_lambda >> gallery_table
    gallery_lambda >> template_bucket
    gallery_lambda >> session_table
    
    # Notification flow
    notification_lambda >> sns_topic
    sns_topic >> Edge(label="Push") >> mobile
    eventbridge >> Edge(label="Trigger") >> notification_lambda
    
    # Event processing
    sqs_standard >> Edge(label="Async", style="dashed") >> [ai_lambda, notification_lambda]
    sqs_fifo >> Edge(label="Ordered") >> upload_lambda
    
    # Monitoring connections
    [auth_lambda, upload_lambda, ai_lambda, user_lambda, gallery_lambda] >> Edge(style="dotted") >> cloudwatch
    api >> Edge(style="dotted") >> xray
    cloudwatch >> alarms
    
    # Cache connections
    [user_lambda, gallery_lambda, auth_lambda] >> Edge(label="Cache", style="dashed") >> redis
    
    # Static assets
    cdn >> Edge(label="Static", style="dashed") >> static_bucket

print("AWS infrastructure diagram generated as 'aws_infrastructure_diagram.png'")