#!/bin/bash
# Quick script to build the frontend or create a placeholder

set -e

cd "$(dirname "$0")/.."

echo "======================================"
echo "Frontend Build Check"
echo "======================================"

if [ -d "frontend/dist" ]; then
    echo "[OK] Frontend already built (frontend/dist exists)"
    exit 0
fi

echo ""
echo "Frontend not built. Choose an option:"
echo ""
echo "1. Build frontend (requires Node.js 16+)"
echo "2. Create placeholder (backend-only mode, no web UI)"
echo ""
read -p "Enter choice (1 or 2): " choice

case $choice in
    1)
        echo ""
        echo "Building frontend..."
        cd frontend
        
        # Check if Node.js is installed
        if ! command -v node &> /dev/null; then
            echo "ERROR: Node.js not found"
            echo ""
            echo "Install Node.js:"
            echo "  curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -"
            echo "  sudo apt-get install -y nodejs"
            exit 1
        fi
        
        echo "Installing dependencies..."
        npm install
        
        echo "Building..."
        npm run build
        
        echo ""
        echo "[OK] Frontend built successfully"
        ;;
    2)
        echo ""
        echo "Creating placeholder frontend..."
        mkdir -p frontend/dist
        cat > frontend/dist/index.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>NeuroInsight - Backend Only</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 { color: #2563eb; }
        code {
            background: #f1f5f9;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
        }
        .api-link {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background: #2563eb;
            color: white;
            text-decoration: none;
            border-radius: 4px;
        }
        .api-link:hover {
            background: #1d4ed8;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>NeuroInsight API Server</h1>
        <p>This container is running in <strong>backend-only mode</strong>.</p>
        <p>The web UI frontend was not built during image creation.</p>
        
        <h2>API Endpoints</h2>
        <ul>
            <li><code>GET /api/health</code> - Health check</li>
            <li><code>GET /api/jobs</code> - List all jobs</li>
            <li><code>POST /api/upload</code> - Upload MRI file</li>
            <li><code>GET /api/jobs/{job_id}</code> - Get job status</li>
        </ul>
        
        <a href="/docs" class="api-link">View API Documentation</a>
        
        <h2>To enable Web UI:</h2>
        <ol>
            <li>Install Node.js 16+ on build machine</li>
            <li>Run: <code>cd frontend && npm install && npm run build</code></li>
            <li>Rebuild Docker image: <code>cd deploy && ./build.sh</code></li>
        </ol>
    </div>
</body>
</html>
EOF
        echo "[OK] Placeholder created"
        echo ""
        echo "Note: Web UI will not be available, but API will work"
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac
