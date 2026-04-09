# VONIKO Factory Management System - Deployment Configuration

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
python scripts/database/init_db.py

# Run development server
python main.py
```

Access at http://localhost:8000

## Docker Deployment

```bash
# Build image
docker build -t voniko-factory .

# Run container
docker run -d -p 8000:8000 -v $(pwd)/uploads:/app/uploads -v $(pwd)/voniko.db:/app/voniko.db voniko-factory
```

## Cloudflare Deployment (Recommended)

### Option 1: Cloudflare Tunnel (Secure)

1. Install cloudflared:
```bash
# Windows
winget install --id Cloudflare.cloudflared

# Linux
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloudflare-main.gpg
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared focal main' | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update && sudo apt install cloudflared
```

2. Login and create tunnel:
```bash
cloudflared tunnel login
cloudflared tunnel create voniko-factory
```

3. Configure tunnel (config.yml):
```yaml
tunnel: <TUNNEL_ID>
credentials-file: /path/to/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: voniko.vn
    service: http://localhost:8000
  - service: http_status:404
```

4. Run tunnel:
```bash
cloudflared tunnel run voniko-factory
```

### Option 2: Cloudflare Workers (Static + API Proxy)

Not recommended for this stack due to SQLite database requirements.

## Production Configuration

### Environment Variables

Create `.env` file:
```env
# Database (for PostgreSQL migration)
DATABASE_URL=postgresql://user:password@host:5432/voniko

# JWT Secret (change in production!)
JWT_SECRET_KEY=your-super-secret-key-change-me

# CORS Origins
CORS_ORIGINS=https://voniko.vn,https://www.voniko.vn

# Upload directory
UPLOAD_DIR=/app/uploads
```

### Nginx Reverse Proxy (Alternative)

```nginx
server {
    listen 80;
    server_name voniko.vn www.voniko.vn;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /static {
        alias /path/to/EngineerSystem/static;
        expires 7d;
    }
    
    location /uploads {
        alias /path/to/EngineerSystem/uploads;
        expires 1d;
    }
}
```

### SSL with Let's Encrypt

```bash
sudo certbot --nginx -d voniko.vn -d www.voniko.vn
```

## Database Migration (Production)

For production, migrate from SQLite to PostgreSQL:

1. Install asyncpg:
```bash
pip install asyncpg psycopg2-binary
```

2. Update DATABASE_URL in .env

3. Run migration (example with alembic):
```bash
alembic upgrade head
```

## Performance Optimization

1. **Gzip Compression** - Enabled via Nginx or middleware
2. **Static File Caching** - 7-day cache headers
3. **Database Connection Pooling** - SQLAlchemy pool_size
4. **CDN for Static Assets** - Cloudflare automatic
5. **Image Compression** - Use WebP format

## Health Check

```bash
curl http://localhost:8000/health
# {"status": "healthy", "version": "1.0.0"}
```
