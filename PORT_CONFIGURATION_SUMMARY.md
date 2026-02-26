# MCQ Generator Port Configuration Summary

## Overview

Successfully implemented strict port configuration starting from **7560** with support for multiple instances and scaling capabilities.

## Port Configuration

### Base Port: 7560
- **Primary Instance**: Port 7560
- **Additional Instances**: Ports 7561, 7562, 7563, ... (up to 7569)
- **Total Supported**: 10 concurrent instances (7560-7569)

## Container Configuration

### Updated Files
1. **Dockerfile**: 
   - Changed EXPOSE from 8000 to 7560
   - Updated CMD to use port 7560
   - Updated health check to use port 7560

2. **docker-compose.yml**:
   - Instance 1: Port 7560 (default)
   - Instance 2: Port 7561 (multi-instance profile)
   - Instance 3: Port 7562 (multi-instance profile)
   - All instances share Redis backend

3. **docker-compose.scale.yml**:
   - Additional instances 4-10 (ports 7563-7569)
   - Load balancer configuration with nginx

## Deployment Options

### 1. Single Instance (Default)
```bash
docker compose up -d
# Access: http://localhost:7560
```

### 2. Multiple Instances
```bash
# Start 3 instances
docker compose --profile multi-instance up -d
# Access: http://localhost:7560, http://localhost:7561, http://localhost:7562
```

### 3. Dynamic Scaling
```bash
# Scale up
python3 scale_instances.py up --count 2

# Scale down
python3 scale_instances.py down --count 1

# Check status
python3 scale_instances.py status
```

### 4. Load Balanced
```bash
# Start with nginx load balancer
docker compose --profile load-balanced up -d
# Single entry point: http://localhost:7560
```

## Management Tools

### Scaling Script (`scale_instances.py`)
- **Purpose**: Dynamic instance management
- **Features**:
  - Scale up/down instances
  - Health monitoring
  - Status reporting
  - Port management (7560+)

### Multi-Port Testing (`test_multi_port.py`)
- **Purpose**: Test all instances concurrently
- **Features**:
  - Parallel health checks
  - Endpoint validation
  - Watch mode for continuous monitoring
  - Formatted reporting

## Current Status

### ✅ Running Instances
- **Instance 1**: Port 7560 - 🟢 HEALTHY
- **Instance 2**: Port 7561 - 🟢 HEALTHY  
- **Instance 3**: Port 7562 - 🟢 HEALTHY

### 📊 Test Results
- **Total Tested**: 3/10 instances
- **Healthy**: 3/3 running instances
- **Success Rate**: 100%

### 🔗 Accessible Endpoints
- **Instance 1**: http://localhost:7560/docs
- **Instance 2**: http://localhost:7561/docs
- **Instance 3**: http://localhost:7562/docs

## Port Allocation Strategy

### Port Mapping
| Instance | Container Port | Host Port | Status |
|----------|---------------|-----------|---------|
| 1 | 7560 | 7560 | ✅ Running |
| 2 | 7560 | 7561 | ✅ Running |
| 3 | 7560 | 7562 | ✅ Running |
| 4 | 7560 | 7563 | Available |
| 5 | 7560 | 7564 | Available |
| 6 | 7560 | 7565 | Available |
| 7 | 7560 | 7566 | Available |
| 8 | 7560 | 7567 | Available |
| 9 | 7560 | 7568 | Available |
| 10 | 7560 | 7569 | Available |

### Environment Variables
- `API_PORT`: Dynamic port assignment per instance
- `INSTANCE_ID`: Unique identifier for each instance
- `CORS_ORIGINS`: Updated to include all ports

## Load Balancer Configuration

### Nginx Setup
- **Upstream Servers**: Round-robin load balancing
- **Health Checks**: Built-in failover
- **Rate Limiting**: 10 requests/second
- **Timeouts**: 30s for connect/send/read

### Features
- **Least Connection**: Routes to least busy instance
- **Failover**: Automatic failover on unhealthy instances
- **Rate Limiting**: Prevents abuse
- **Health Monitoring**: Continuous health checks

## Monitoring and Management

### Health Checks
All instances expose:
- `/health` - Basic health status
- `/healthz` - Kubernetes compatible
- `/ready` - Readiness probe

### Metrics
- **Instance Status**: Real-time monitoring
- **Response Times**: Performance tracking
- **Error Rates**: Failure monitoring

## Usage Examples

### Basic Usage
```bash
# Start primary instance
docker compose up -d mcq-generator-1

# Test endpoint
curl http://localhost:7560/health
```

### Scaling Operations
```bash
# Add 2 more instances
python3 scale_instances.py up --count 2

# Check all instances
python3 test_multi_port.py

# Scale down to 1 instance
python3 scale_instances.py down --count 2
```

### Load Testing
```bash
# Test with load balancer
docker compose --profile load-balanced up -d

# Monitor all instances
python3 test_multi_port.py --watch
```

## Benefits

### ✅ Strict Port Management
- Fixed base port (7560)
- Predictable port allocation
- No port conflicts

### ✅ Scalability
- Up to 10 concurrent instances
- Dynamic scaling
- Load balancing support

### ✅ Monitoring
- Health checks for all instances
- Real-time status reporting
- Automated testing

### ✅ Management Tools
- Simple scaling commands
- Multi-port testing
- Status monitoring

## Next Steps

1. **Production Deployment**: Configure production-ready settings
2. **Monitoring**: Add Prometheus metrics and Grafana dashboards
3. **Auto-scaling**: Implement automatic scaling based on load
4. **Security**: Add authentication and rate limiting
5. **CI/CD**: Integrate with deployment pipelines

## Summary

The MCQ Generator now strictly runs on port **7560** and supports scaling to multiple instances on consecutive ports (7560-7569). The configuration includes:

- ✅ **Fixed Base Port**: 7560 (strict requirement met)
- ✅ **Multi-Instance Support**: 10 instances maximum
- ✅ **Dynamic Scaling**: Automated instance management
- ✅ **Load Balancing**: Nginx-based load distribution
- ✅ **Health Monitoring**: Comprehensive health checks
- ✅ **Management Tools**: Scaling and testing scripts

The implementation provides a robust, scalable solution that meets the requirement of running strictly on port 7560 and onward.
