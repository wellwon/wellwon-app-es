/**
 * Avatar cache utility для устранения мигания аватарок менеджеров
 * Кэширует загруженные изображения в памяти и sessionStorage
 */

class AvatarCache {
  private loadedUrls = new Set<string>();
  private readonly storageKey = 'avatarLoaded:v1';

  constructor() {
    this.hydrateFromStorage();
  }

  private hydrateFromStorage(): void {
    try {
      const stored = sessionStorage.getItem(this.storageKey);
      if (stored) {
        const urls = JSON.parse(stored) as string[];
        urls.forEach(url => this.loadedUrls.add(url));
      }
    } catch (error) {
      // Игнорируем ошибки восстановления из storage
    }
  }

  private saveToStorage(): void {
    try {
      const urls = Array.from(this.loadedUrls);
      sessionStorage.setItem(this.storageKey, JSON.stringify(urls));
    } catch (error) {
      // Игнорируем ошибки сохранения в storage
    }
  }

  isLoaded(url: string): boolean {
    if (!url) return false;
    return this.loadedUrls.has(url);
  }

  markLoaded(url: string): void {
    if (!url) return;
    
    if (!this.loadedUrls.has(url)) {
      this.loadedUrls.add(url);
      this.saveToStorage();
    }
  }

  async preload(url: string): Promise<void> {
    if (!url || this.isLoaded(url)) {
      return Promise.resolve();
    }

    return new Promise((resolve, reject) => {
      const img = new Image();
      
      img.onload = () => {
        this.markLoaded(url);
        resolve();
      };
      
      img.onerror = () => {
        reject(new Error(`Failed to load image: ${url}`));
      };
      
      img.src = url;
    });
  }

  clear(): void {
    this.loadedUrls.clear();
    try {
      sessionStorage.removeItem(this.storageKey);
    } catch (error) {
      // Игнорируем ошибки
    }
  }
}

export const avatarCache = new AvatarCache();