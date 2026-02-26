// Client-side caching utilities for performance optimization

// Simple in-memory cache with TTL support
class Cache {
  constructor(defaultTTL = 5 * 60 * 1000) { // 5 minutes default
    this.cache = new Map();
    this.defaultTTL = defaultTTL;
  }

  set(key, value, ttl = this.defaultTTL) {
    const expiry = Date.now() + ttl;
    this.cache.set(key, { value, expiry });
  }

  get(key) {
    const item = this.cache.get(key);
    if (!item) return null;
    
    if (Date.now() > item.expiry) {
      this.cache.delete(key);
      return null;
    }
    
    return item.value;
  }

  has(key) {
    const item = this.cache.get(key);
    if (!item) return false;
    
    if (Date.now() > item.expiry) {
      this.cache.delete(key);
      return false;
    }
    
    return true;
  }

  delete(key) {
    return this.cache.delete(key);
  }

  clear() {
    this.cache.clear();
  }

  size() {
    return this.cache.size;
  }
}

// API response cache
export const apiCache = new Cache(10 * 60 * 1000); // 10 minutes

// Quiz data cache
export const quizCache = new Cache(30 * 60 * 1000); // 30 minutes

// User data cache
export const userCache = new Cache(60 * 60 * 1000); // 1 hour

// Static resource cache
export const staticCache = new Cache(24 * 60 * 60 * 1000); // 24 hours

// Cache keys
export const CACHE_KEYS = {
  QUIZ_LIST: 'quiz_list',
  QUIZ_DETAILS: 'quiz_details_',
  USER_PROFILE: 'user_profile_',
  QUIZ_ATTEMPTS: 'quiz_attempts_',
  QUIZ_RESULTS: 'quiz_results_',
  CATEGORIES: 'categories',
  STATISTICS: 'statistics_'
};

// Cache decorator for API calls
export const withCache = (cache, keyGenerator) => {
  return (target, propertyName, descriptor) => {
    const originalMethod = descriptor.value;
    
    descriptor.value = async function(...args) {
      const cacheKey = keyGenerator ? keyGenerator(...args) : propertyName;
      
      // Check cache first
      const cached = cache.get(cacheKey);
      if (cached !== null) {
        console.log(`[Cache] Cache hit for ${cacheKey}`);
        return cached;
      }
      
      console.log(`[Cache] Cache miss for ${cacheKey}`);
      
      // Call original method
      const result = await originalMethod.apply(this, args);
      
      // Cache the result
      cache.set(cacheKey, result);
      
      return result;
    };
    
    return descriptor;
  };
};

// Cache invalidation utilities
export const invalidateCache = (cache, pattern) => {
  if (typeof pattern === 'string') {
    // Invalidate single key
    cache.delete(pattern);
  } else if (pattern instanceof RegExp) {
    // Invalidate keys matching pattern
    for (const key of cache.cache.keys()) {
      if (pattern.test(key)) {
        cache.delete(key);
      }
    }
  }
};

// Batch cache invalidation
export const invalidateBatch = (cache, keys) => {
  keys.forEach(key => cache.delete(key));
};

// Cache warming utilities
export const warmCache = async (cache, dataLoader, keys) => {
  const promises = keys.map(async (key) => {
    try {
      const data = await dataLoader(key);
      cache.set(key, data);
      console.log(`[Cache] Warmed cache for ${key}`);
    } catch (error) {
      console.error(`[Cache] Failed to warm cache for ${key}:`, error);
    }
  });
  
  await Promise.all(promises);
};

// Cache statistics
export const getCacheStats = (cache) => {
  return {
    size: cache.size(),
    keys: Array.from(cache.cache.keys()),
    memoryUsage: JSON.stringify(Array.from(cache.cache.entries())).length
  };
};

// Persistent cache using localStorage
export const persistentCache = {
  set: (key, value, ttl = null) => {
    try {
      const item = {
        value,
        expiry: ttl ? Date.now() + ttl : null
      };
      localStorage.setItem(`cache_${key}`, JSON.stringify(item));
    } catch (error) {
      console.error('[Cache] Failed to set persistent cache:', error);
    }
  },

  get: (key) => {
    try {
      const item = JSON.parse(localStorage.getItem(`cache_${key}`));
      if (!item) return null;
      
      if (item.expiry && Date.now() > item.expiry) {
        localStorage.removeItem(`cache_${key}`);
        return null;
      }
      
      return item.value;
    } catch (error) {
      console.error('[Cache] Failed to get from persistent cache:', error);
      return null;
    }
  },

  delete: (key) => {
    try {
      localStorage.removeItem(`cache_${key}`);
    } catch (error) {
      console.error('[Cache] Failed to delete from persistent cache:', error);
    }
  },

  clear: () => {
    try {
      const keys = Object.keys(localStorage).filter(key => key.startsWith('cache_'));
      keys.forEach(key => localStorage.removeItem(key));
    } catch (error) {
      console.error('[Cache] Failed to clear persistent cache:', error);
    }
  }
};

// Service Worker cache utilities
export const swCache = {
  // Store data in service worker cache
  store: async (key, value, ttl = null) => {
    if ('caches' in window) {
      try {
        const cache = await caches.open('quizme-cache-v1');
        const response = new Response(JSON.stringify({
          value,
          expiry: ttl ? Date.now() + ttl : null
        }));
        await cache.put(key, response);
      } catch (error) {
        console.error('[SW Cache] Failed to store in service worker cache:', error);
      }
    }
  },

  // Retrieve data from service worker cache
  retrieve: async (key) => {
    if ('caches' in window) {
      try {
        const cache = await caches.open('quizme-cache-v1');
        const response = await cache.match(key);
        
        if (!response) return null;
        
        const data = await response.json();
        
        if (data.expiry && Date.now() > data.expiry) {
          await cache.delete(key);
          return null;
        }
        
        return data.value;
      } catch (error) {
        console.error('[SW Cache] Failed to retrieve from service worker cache:', error);
        return null;
      }
    }
    
    return null;
  },

  // Delete from service worker cache
  delete: async (key) => {
    if ('caches' in window) {
      try {
        const cache = await caches.open('quizme-cache-v1');
        await cache.delete(key);
      } catch (error) {
        console.error('[SW Cache] Failed to delete from service worker cache:', error);
      }
    }
  },

  // Clear service worker cache
  clear: async () => {
    if ('caches' in window) {
      try {
        const cacheNames = await caches.keys();
        await Promise.all(
          cacheNames.map(cacheName => caches.delete(cacheName))
        );
      } catch (error) {
        console.error('[SW Cache] Failed to clear service worker cache:', error);
      }
    }
  }
};

// Cache warming strategies
export const warmupStrategies = {
  // Warm up frequently accessed quizzes
  warmPopularQuizzes: async () => {
    const popularQuizIds = ['1', '2', '3', '4', '5']; // These would come from analytics
    const dataLoader = async (quizId) => {
      // In a real app, this would fetch quiz data from API
      return { id: quizId, title: `Quiz ${quizId}`, questions: [] };
    };
    
    await warmCache(quizCache, dataLoader, popularQuizIds.map(id => CACHE_KEYS.QUIZ_DETAILS + id));
  },

  // Warm up user profile data
  warmupUserProfile: async (userId) => {
    const dataLoader = async (id) => {
      // Fetch user profile data
      return { id, name: `User ${id}`, email: `user${id}@example.com` };
    };
    
    await warmCache(userCache, dataLoader, [CACHE_KEYS.USER_PROFILE + userId]);
  },

  // Warm up categories
  warmupCategories: async () => {
    const dataLoader = async () => {
      return [
        { id: 1, name: 'Science' },
        { id: 2, name: 'Mathematics' },
        { id: 3, name: 'History' }
      ];
    };
    
    await warmCache(staticCache, dataLoader, [CACHE_KEYS.CATEGORIES]);
  }
};

// Cache cleanup utilities
export const cleanupExpiredCache = (cache) => {
  const now = Date.now();
  const keysToDelete = [];
  
  for (const [key, item] of cache.cache.entries()) {
    if (item.expiry && now > item.expiry) {
      keysToDelete.push(key);
    }
  }
  
  keysToDelete.forEach(key => cache.delete(key));
  
  console.log(`[Cache] Cleaned up ${keysToDelete.length} expired cache entries`);
};

// Export cache instances
export default {
  apiCache,
  quizCache,
  userCache,
  staticCache,
  persistentCache,
  swCache
};
