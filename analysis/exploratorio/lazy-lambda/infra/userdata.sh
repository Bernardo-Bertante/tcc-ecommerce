#!/bin/bash
mkdir -p /opt/exp-lazy
aws s3 cp --region us-east-1 --recursive s3://exp-lazy-results-776648109551/_driver/ /opt/exp-lazy/
chmod +x /opt/exp-lazy/*.sh
echo "userdata done $(date -Is)" > /opt/exp-lazy/USERDATA_OK
