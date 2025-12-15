#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Spartan Coach - GCP Deployment Script
# ═══════════════════════════════════════════════════════════════

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${RED}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${RED}   SPARTAN COACH - DEPLOYMENT TO GOOGLE CLOUD PLATFORM${NC}"
echo -e "${RED}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}ERROR: gcloud CLI is not installed.${NC}"
    echo "Please install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is logged in
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n 1 &> /dev/null; then
    echo -e "${YELLOW}You need to login to Google Cloud first.${NC}"
    gcloud auth login
fi

# Get or set project ID
echo -e "${YELLOW}Available GCP Projects:${NC}"
gcloud projects list --format="table(projectId,name)"
echo ""

read -p "Enter your GCP Project ID: " PROJECT_ID

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: Project ID cannot be empty.${NC}"
    exit 1
fi

# Set the project
echo -e "${GREEN}Setting project to: $PROJECT_ID${NC}"
gcloud config set project $PROJECT_ID

# Enable required APIs
echo ""
echo -e "${YELLOW}Enabling required GCP APIs...${NC}"
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable secretmanager.googleapis.com

# Set region
REGION="us-central1"
echo -e "${GREEN}Using region: $REGION${NC}"

# Check for .env file and create secrets
echo ""
echo -e "${YELLOW}Setting up secrets...${NC}"

if [ -f ".env" ]; then
    echo "Found .env file. Creating secrets in Secret Manager..."

    # Read important env vars and create secrets
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ $key =~ ^#.*$ ]] && continue
        [[ -z $key ]] && continue

        # Remove quotes from value
        value=$(echo "$value" | tr -d '"' | tr -d "'")

        if [ ! -z "$value" ]; then
            echo "Creating secret: $key"
            echo -n "$value" | gcloud secrets create "$key" --data-file=- --replication-policy="automatic" 2>/dev/null || \
            echo -n "$value" | gcloud secrets versions add "$key" --data-file=-
        fi
    done < .env
else
    echo -e "${YELLOW}No .env file found. You'll need to set secrets manually.${NC}"
    echo "Required secrets:"
    echo "  - ANTHROPIC_API_KEY"
    echo "  - GOOGLE_CLIENT_ID"
    echo "  - GOOGLE_CLIENT_SECRET"
    echo "  - SECRET_KEY"
    echo "  - DEFAULT_USERNAME"
    echo "  - DEFAULT_PASSWORD"
fi

# Build and deploy options
echo ""
echo -e "${YELLOW}Choose deployment method:${NC}"
echo "1) Quick Deploy (Cloud Build - recommended)"
echo "2) Manual Deploy (build locally, push to GCR)"
echo ""
read -p "Enter choice [1]: " DEPLOY_CHOICE
DEPLOY_CHOICE=${DEPLOY_CHOICE:-1}

if [ "$DEPLOY_CHOICE" = "1" ]; then
    # Cloud Build deployment
    echo ""
    echo -e "${GREEN}Starting Cloud Build deployment...${NC}"

    gcloud builds submit --config=cloudbuild.yaml \
        --substitutions=_REGION=$REGION

else
    # Manual deployment
    echo ""
    echo -e "${GREEN}Building Docker image locally...${NC}"

    IMAGE_NAME="gcr.io/$PROJECT_ID/spartan-coach"

    docker build -t $IMAGE_NAME:latest .

    echo -e "${GREEN}Pushing to Google Container Registry...${NC}"
    docker push $IMAGE_NAME:latest

    echo -e "${GREEN}Deploying to Cloud Run...${NC}"
    gcloud run deploy spartan-coach \
        --image $IMAGE_NAME:latest \
        --region $REGION \
        --platform managed \
        --allow-unauthenticated \
        --memory 1Gi \
        --cpu 1 \
        --min-instances 1 \
        --max-instances 10 \
        --set-env-vars "ENVIRONMENT=production"
fi

# Get the service URL
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}   DEPLOYMENT COMPLETE!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

SERVICE_URL=$(gcloud run services describe spartan-coach --region $REGION --format 'value(status.url)')
echo -e "${GREEN}Your Spartan Coach is deployed at:${NC}"
echo -e "${YELLOW}$SERVICE_URL${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Update your OAuth redirect URIs in Google Cloud Console to include:"
echo "   $SERVICE_URL/auth/google/callback"
echo ""
echo "2. Set environment variables in Cloud Run:"
echo "   gcloud run services update spartan-coach --region $REGION \\"
echo "     --set-env-vars \"ANTHROPIC_API_KEY=your-key\""
echo ""
echo "3. Or use Secret Manager references:"
echo "   gcloud run services update spartan-coach --region $REGION \\"
echo "     --set-secrets \"ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest\""
echo ""
echo -e "${RED}EXECUTE YOUR DEPLOYMENT. THE SPARTAN COACH AWAITS.${NC}"
