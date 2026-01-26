import http from '@ohos.net.http';
import fileIO from '@ohos.file.fs';
import common from '@ohos.app.ability.common';
import util from '@ohos.util';

/**
 * 图片缓存工具类
 */
export class ImageCacheUtil {
  private static cacheDir: string = '';
  private static initialized: boolean = false;

  /**
   * 初始化缓存目录
   */
  static async initCacheDir(context: common.Context): Promise<void> {
    if (ImageCacheUtil.initialized) {
      return;
    }
    try {
      const cacheDirPath = context.cacheDir;
      ImageCacheUtil.cacheDir = cacheDirPath + '/image_cache';
      // 确保缓存目录存在
      if (!fileIO.accessSync(ImageCacheUtil.cacheDir)) {
        fileIO.mkdirSync(ImageCacheUtil.cacheDir, true);
      }
      ImageCacheUtil.initialized = true;
      console.info('ImageCacheUtil: 缓存目录初始化成功', ImageCacheUtil.cacheDir);
    } catch (error) {
      console.error('ImageCacheUtil: 初始化缓存目录失败', error);
    }
  }

  /**
   * 生成URL的哈希值作为文件名
   */
  private static async generateFileName(url: string): Promise<string> {
    try {
      // 使用简单的哈希算法替代 cryptoFramework
      let hash = 0;
      for (let i = 0; i < url.length; i++) {
        const char = url.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // Convert to 32bit integer
      }
      const hashHex = Math.abs(hash).toString(16).padStart(8, '0');

      // 从URL中提取文件扩展名
      const lastDotIndex = url.lastIndexOf('.');
      const lastSlashIndex = url.lastIndexOf('/');
      let ext = '.jpg';
      if (lastDotIndex > lastSlashIndex && lastDotIndex !== -1) {
        ext = url.substring(lastDotIndex);
      }
      return hashHex + (ext || '.jpg');
    } catch (error) {
      console.error('ImageCacheUtil: 生成文件名失败', error);
      // 如果失败，使用简单的哈希
      return url.replace(/[^a-zA-Z0-9]/g, '_') + '.jpg';
    }
  }

  /**
   * 获取缓存文件路径
   */
  private static getCacheFilePath(fileName: string): string {
    return ImageCacheUtil.cacheDir + '/' + fileName;
  }

  /**
   * 检查图片是否已缓存
   */
  static async isImageCached(url: string): Promise<boolean> {
    try {
      const fileName = await ImageCacheUtil.generateFileName(url);
      const cachePath = ImageCacheUtil.getCacheFilePath(fileName);
      return fileIO.accessSync(cachePath);
    } catch (error) {
      console.error('ImageCacheUtil: 检查缓存失败', error);
      return false;
    }
  }

  /**
   * 获取缓存的图片路径，如果不存在则返回null
   */
  static async getCachedImagePath(url: string): Promise<string | null> {
    try {
      const fileName = await ImageCacheUtil.generateFileName(url);
      const cachePath = ImageCacheUtil.getCacheFilePath(fileName);
      if (fileIO.accessSync(cachePath)) {
        return cachePath;
      }
      return null;
    } catch (error) {
      console.error('ImageCacheUtil: 获取缓存路径失败', error);
      return null;
    }
  }

  /**
   * 下载图片并保存到缓存
   */
  static async downloadAndCache(url: string): Promise<string> {
    try {
      // 先检查是否已缓存
      const cachedPath = await ImageCacheUtil.getCachedImagePath(url);
      if (cachedPath) {
        console.info('ImageCacheUtil: 图片已缓存，使用缓存', url);
        return cachedPath;
      }

      console.info('ImageCacheUtil: 开始下载图片', url);
      const httpRequest = http.createHttp();
      const response = await httpRequest.request(url, {
        method: http.RequestMethod.GET,
        header: {
          'Content-Type': 'image/*'
        },
        connectTimeout: 20000,
        readTimeout: 20000
      });

      if (response.responseCode === http.ResponseCode.OK && response.result) {
        const fileName = await ImageCacheUtil.generateFileName(url);
        const cachePath = ImageCacheUtil.getCacheFilePath(fileName);

        // 将图片数据写入文件
        const file =
          fileIO.openSync(cachePath, fileIO.OpenMode.CREATE | fileIO.OpenMode.WRITE_ONLY | fileIO.OpenMode.TRUNC);
        let dataToWrite: ArrayBuffer;
        if (response.result) {
          // 直接使用response.result作为ArrayBuffer
          dataToWrite = response.result as ArrayBuffer;
        } else {
          throw new Error('响应数据为空');
        }

        fileIO.writeSync(file.fd, dataToWrite);
        fileIO.closeSync(file);

        console.info('ImageCacheUtil: 图片下载并缓存成功', cachePath);
        httpRequest.destroy();
        return cachePath;
      } else {
        httpRequest.destroy();
        throw new Error(`下载失败，响应码: ${response.responseCode}`);
      }
    } catch (error) {
      console.error('ImageCacheUtil: 下载图片失败', error);
      if (error instanceof Error) {
        throw error;
      } else {
        throw new Error(String(error));
      }
    }
  }

  /**
   * 清除所有缓存
   */
  static async clearCache(): Promise<void> {
    try {
      if (!ImageCacheUtil.initialized || !fileIO.accessSync(ImageCacheUtil.cacheDir)) {
        return;
      }
      const files = fileIO.listFileSync(ImageCacheUtil.cacheDir);
      for (let file of files) {
        const filePath = ImageCacheUtil.cacheDir + '/' + file;
        fileIO.unlinkSync(filePath);
      }
      console.info('ImageCacheUtil: 缓存已清除');
    } catch (error) {
      console.error('ImageCacheUtil: 清除缓存失败', error);
    }
  }

  /**
   * 获取缓存大小（字节）
   */
  static async getCacheSize(): Promise<number> {
    try {
      if (!ImageCacheUtil.initialized || !fileIO.accessSync(ImageCacheUtil.cacheDir)) {
        return 0;
      }
      let totalSize = 0;
      const files = fileIO.listFileSync(ImageCacheUtil.cacheDir);
      for (let file of files) {
        const filePath = ImageCacheUtil.cacheDir + '/' + file;
        const stat = fileIO.statSync(filePath);
        totalSize += stat.size;
      }
      return totalSize;
    } catch (error) {
      console.error('ImageCacheUtil: 获取缓存大小失败', error);
      return 0;
    }
  }
}

