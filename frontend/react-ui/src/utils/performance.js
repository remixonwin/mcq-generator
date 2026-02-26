// Performance monitoring and optimization utilities

// Performance monitoring
export const measurePerformance = (name, fn) => {
  const start = performance.now();
  const result = fn();
  const end = performance.now();
  const duration = end - start;
  
  // Log performance metrics
  console.log(`[Performance] ${name}: ${duration.toFixed(2)}ms`);
  
  // Send to monitoring service in production
  if (process.env.NODE_ENV === 'production') {
    // Send metrics to monitoring service
    sendPerformanceMetric(name, duration);
  }
  
  return result;
};

// Debounce function for performance optimization
export const debounce = (func, wait) => {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      timeout = setTimeout(() => func(...args), wait);
    };
    clearTimeout(timeout);
    return later();
  };
};

// Throttle function for performance optimization
export const throttle = (func, limit) => {
  let inThrottle;
  return function executedFunction(...args) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => {
        inThrottle = false;
      }, limit);
    }
  };
};

// Memoization for expensive computations
export const memoize = (fn) => {
  const cache = new Map();
  return (...args) => {
    const key = JSON.stringify(args);
    if (cache.has(key)) {
      return cache.get(key);
    }
    const result = fn(...args);
    cache.set(key, result);
    return result;
  };
};

// Image optimization
export const optimizeImage = (src, options = {}) => {
  const {
    width = 800,
    height = 600,
    quality = 80,
    format = 'webp'
  } = options;

  // Return optimized image URL
  if (src.startsWith('http')) {
    return `${src}?w=${width}&h=${height}&q=${quality}&f=${format}`;
  }
  
  return src;
};

// Lazy loading for images
export const lazyLoadImage = (src, options = {}) => {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(optimizeImage(src, options));
    img.onerror = () => reject(new Error('Failed to load image'));
    img.src = src;
  });
};

// Bundle size monitoring
export const getBundleSize = () => {
  if (process.env.NODE_ENV === 'development') {
    // Development: estimate bundle size
    const scripts = document.querySelectorAll('script[src]');
    let totalSize = 0;
    
    scripts.forEach(script => {
      if (script.src) {
        fetch(script.src)
          .then(response => response.headers.get('content-length'))
          .then(size => {
            totalSize += parseInt(size, 10);
          })
          .catch(() => {});
      }
    });
    
    return totalSize;
  }
  
  return 0;
};

// Performance metrics collection
export const collectMetrics = () => {
  if (typeof window !== 'undefined' && 'performance' in window) {
    const navigation = performance.getEntriesByType('navigation')[0];
    const paint = performance.getEntriesByType('paint')[0];
    
    const metrics = {
      // Navigation timing
      domContentLoaded: navigation?.domContentLoadedEventEnd - navigation?.navigationStart,
      loadComplete: navigation?.loadEventEnd - navigation?.navigationStart,
      firstPaint: paint?.startTime - navigation?.navigationStart,
      
      // Resource timing
      resourceCount: performance.getEntriesByType('resource').length,
      
      // Memory usage
      memoryUsed: performance.memory?.usedJSHeapSize,
      memoryTotal: performance.memory?.totalJSHeapSize,
      
      // Network information
      connectionType: navigator.connection?.effectiveType,
      downlink: navigator.connection?.downlink,
      rtt: navigator.connection?.rtt
    };
    
    return metrics;
  }
  
  return {};
};

// Send performance metrics to monitoring service
export const sendPerformanceMetric = (name, value) => {
  if (process.env.NODE_ENV === 'production' && window.gtag) {
    // Send to Google Analytics
    window.gtag('event', 'performance_metric', {
      event_category: 'Performance',
      event_label: name,
      value: Math.round(value),
      custom_parameter: {
        metric_type: name.includes('time') ? 'duration' : 'count'
      }
    });
  }
};

// Performance observer setup
export const setupPerformanceObserver = () => {
  if (typeof window !== 'undefined' && 'PerformanceObserver' in window) {
    // Observe largest contentful paint
    const lcpObserver = new PerformanceObserver((entryList) => {
      const entries = entryList.getEntries();
      const lastEntry = entries[entries.length - 1];
      console.log('[Performance] LCP:', lastEntry.startTime);
      sendPerformanceMetric('largest_contentful_paint', lastEntry.startTime);
    });
    lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] });

    // Observe first contentful paint
    const fcpObserver = new PerformanceObserver((entryList) => {
      const entries = entryList.getEntries();
      const firstEntry = entries[0];
      console.log('[Performance] FCP:', firstEntry.startTime);
      sendPerformanceMetric('first_contentful_paint', firstEntry.startTime);
    });
    fcpObserver.observe({ entryTypes: ['first-contentful-paint'] });

    // Observe time to interactive
    const ttiObserver = new PerformanceObserver((entryList) => {
      const entries = entryList.getEntries();
      const ttiEntry = entries.find(entry => entry.name === 'time-to-interactive');
      if (ttiEntry) {
        console.log('[Performance] TTI:', ttiEntry.startTime);
        sendPerformanceMetric('time_to_interactive', ttiEntry.startTime);
      }
    });
    ttiObserver.observe({ entryTypes: ['measure'] });
  }
};

// Component performance monitoring HOC
export const withPerformanceMonitoring = (WrappedComponent, componentName) => {
  return (props) => {
    const renderStart = performance.now();
    
    // Measure render performance
    const renderTime = measurePerformance(
      `render_${componentName}`,
      () => WrappedComponent(props)
    );
    
    return renderTime;
  };
};

// Resource loading optimization
export const preloadResources = (resources) => {
  if (typeof window !== 'undefined' && 'requestIdleCallback' in window) {
    window.requestIdleCallback(() => {
      resources.forEach(resource => {
        if (resource.type === 'image') {
          lazyLoadImage(resource.src);
        } else if (resource.type === 'script') {
          const link = document.createElement('link');
          link.rel = 'preload';
          link.as = 'script';
          link.href = resource.src;
          document.head.appendChild(link);
        }
      });
    });
  }
};

// Critical path optimization
export const optimizeCriticalPath = () => {
  // Preload critical resources
  const criticalResources = [
    { type: 'script', src: '/api/health' },
    { type: 'image', src: '/images/logo.png' }
  ];
  
  preloadResources(criticalResources);
  
  // Setup performance observers
  setupPerformanceObserver();
};

// Performance budget validation
export const validatePerformanceBudget = (metrics) => {
  const budget = {
    bundleSize: 1024 * 1024, // 1MB
    loadTime: 3000, // 3 seconds
    firstPaint: 1500, // 1.5 seconds
    largestContentfulPaint: 2500, // 2.5 seconds
    timeToInteractive: 3500 // 3.5 seconds
  };

  const violations = [];

  if (metrics.bundleSize > budget.bundleSize) {
    violations.push(`Bundle size ${(metrics.bundleSize / 1024 / 1024).toFixed(2)}MB exceeds budget of ${(budget.bundleSize / 1024 / 1024).toFixed(2)}MB`);
  }

  if (metrics.loadComplete > budget.loadTime) {
    violations.push(`Load time ${metrics.loadComplete}ms exceeds budget of ${budget.loadTime}ms`);
  }

  if (metrics.firstPaint > budget.firstPaint) {
    violations.push(`First paint ${metrics.firstPaint}ms exceeds budget of ${budget.firstPaint}ms`);
  }

  if (metrics.largestContentfulPaint > budget.largestContentfulPaint) {
    violations.push(`LCP ${metrics.largestContentfulPaint}ms exceeds budget of ${budget.largestContentfulPaint}ms`);
  }

  if (metrics.timeToInteractive > budget.timeToInteractive) {
    violations.push(`TTI ${metrics.timeToInteractive}ms exceeds budget of ${budget.timeToInteractive}ms`);
  }

  return {
    passed: violations.length === 0,
    violations,
    budget
  };
};
