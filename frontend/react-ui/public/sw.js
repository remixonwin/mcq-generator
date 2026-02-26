// Service Worker for QuizMe application
const CACHE_NAME = 'quizme-cache-v1';
const STATIC_CACHE = 'quizme-static-v1';
const API_CACHE = 'quizme-api-v1';

// Cache names for different types of content
const CACHE_URLS = [
  STATIC_CACHE,
  API_CACHE
];

// Files to cache for offline functionality
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/favicon.ico',
  '/images/',
  '/icons/',
  '/fonts/'
];

// API endpoints to cache
const API_ENDPOINTS = [
  '/api/v1/quizzes',
  '/api/v1/categories',
  '/api/v1/users/profile'
];

// Install event listeners
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll([
        // Cache static assets
        new Request('/'),
        ...STATIC_ASSETS.map(asset => new Request(asset))
      ]);
    })
  );
});

// Activate event listener
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// Fetch event listener with caching strategy
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url, self.location.origin);

  // Handle static assets
  if (request.method === 'GET') {
    const isStaticAsset = STATIC_ASSETS.some(asset => url.pathname.startsWith(asset));
    
    if (isStaticAsset) {
      event.respondWith(
        caches.match(request).then((response) => {
          return response || fetch(request);
        })
      );
      return;
    }
  }

  // Handle API requests
  if (request.method === 'GET' && API_ENDPOINTS.some(endpoint => url.pathname.startsWith(endpoint))) {
    event.respondWith(
      caches.match(request).then((response) => {
        if (response) {
          // Return cached response if it's not too old
          const responseDate = response.headers.get('date');
          const cacheAge = responseDate ? Date.now() - new Date(responseDate).getTime() : 0;
          
          // Cache API responses for 5 minutes
          if (cacheAge < 5 * 60 * 1000) {
            return response;
          }
        }
        
        // Fetch from network and cache the response
        return fetch(request).then((response) => {
          // Cache successful GET requests
          if (response.ok) {
            const responseClone = response.clone();
            caches.open(API_CACHE).then((cache) => {
              cache.put(request, responseClone);
            });
          }
          return response;
        });
      })
    );
  }
});

// Background sync for offline functionality
self.addEventListener('sync', (event) => {
  if (event.tag === 'background-sync') {
    event.waitUntil(
      caches.open(CACHE_NAME).then((cache) => {
        return cache.keys().then((cacheKeys) => {
          return Promise.all(
            cacheKeys.map((cacheKey) => {
              return caches.match(cacheKey).then((response) => {
                if (response) {
                  return caches.delete(cacheKey);
                }
              });
            })
          );
        });
      })
    );
  }
});

// Push notification handler
self.addEventListener('push', (event) => {
  const options = {
    body: event.data.text(),
    icon: '/icons/icon-192x192.png',
    badge: '/icons/badge-72x72.png',
    vibrate: [100, 50, 100],
    data: {
      dateOfArrival: Date.now(),
      url: event.target.url
    },
    actions: [{
      action: 'navigate',
      url: '/',
      title: 'QuizMe'
    }]
  };

  event.waitUntil(
    self.registration.showNotification('QuizMe', options)
  );
});

// Message handler for cache management
self.addEventListener('message', (event) => {
  const { type, payload } = event.data;

  switch (type) {
    case 'CACHE_UPDATE':
      // Update cache with new data
      updateCache(payload.key, payload.data, payload.ttl);
      break;
    
    case 'CACHE_INVALIDATE':
      // Invalidate cache entries
      invalidateCache(payload.pattern);
      break;
    
    case 'CACHE_CLEAR':
      // Clear all caches
      clearAllCaches();
      break;
    
    default:
      console.log('[SW] Unknown message type:', type);
  }
});

// Update cache helper function
async function updateCache(key, data, ttl) {
  try {
    const cache = await caches.open(CACHE_NAME);
    const response = new Response(JSON.stringify({
      value: data,
      expiry: ttl ? Date.now() + ttl : null
    }));
    await cache.put(key, response);
    console.log('[SW] Cache updated for:', key);
  } catch (error) {
    console.error('[SW] Failed to update cache:', error);
  }
}

// Invalidate cache helper function
async function invalidateCache(pattern) {
  try {
    const cache = await caches.open(CACHE_NAME);
    const keys = await cache.keys();
    
    const keysToDelete = keys.filter(key => {
      if (typeof pattern === 'string') {
        return key === pattern;
      } else if (pattern instanceof RegExp) {
        return pattern.test(key);
      }
      return false;
    });
    
    await Promise.all(
      keysToDelete.map(key => cache.delete(key))
    );
    
    console.log('[SW] Cache invalidated for pattern:', pattern);
  } catch (error) {
    console.error('[SW] Failed to invalidate cache:', error);
  }
}

// Clear all caches helper function
async function clearAllCaches() {
  try {
    const cacheNames = await caches.keys();
    await Promise.all(
      cacheNames.map(cacheName => caches.delete(cacheName))
    );
    console.log('[SW] All caches cleared');
  } catch (error) {
    console.error('[SW] Failed to clear caches:', error);
  }
}

// Performance monitoring
self.addEventListener('message', (event) => {
  if (event.data.type === 'PERFORMANCE_METRIC') {
    const { name, value } = event.data;
    console.log('[SW] Performance metric:', name, value);
    
    // Send to Google Analytics if available
    if (self.gtag) {
      self.gtag('event', 'performance_metric', {
        event_category: 'Performance',
        event_label: name,
        value: Math.round(value),
        custom_parameter: {
          location: 'service_worker'
        }
      });
    }
  }
});
