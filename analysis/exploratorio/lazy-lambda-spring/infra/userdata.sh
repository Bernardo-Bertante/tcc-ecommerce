#!/bin/bash
mkdir -p /opt/exp-lazy-sb
aws s3 cp --region us-east-1 --recursive s3://exp-lazy-sb-results-776648109551/_driver/ /opt/exp-lazy-sb/
chmod +x /opt/exp-lazy-sb/*.sh
echo "userdata done $(date -Is)" > /opt/exp-lazy-sb/USERDATA_OK
