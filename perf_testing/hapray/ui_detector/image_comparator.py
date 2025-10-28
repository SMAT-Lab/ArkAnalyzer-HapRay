"""
Copyright (c) 2025 Huawei Device Co., Ltd.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


class RegionImageComparator:
    def __init__(self):
        self.hash_size = 8  # dHash尺寸，生成64位哈希值

    def load_and_crop_region(self, image_path, region):
        """
        加载图像并裁剪指定区域

        Args:
            image_path: 图像路径
            region: 区域坐标 (x1, y1, x2, y2)

        Returns:
            裁剪后的图像区域
        """
        try:
            # 使用PIL加载图像
            img = Image.open(image_path)
            img = img.convert('RGB')

            # 裁剪指定区域
            cropped = img.crop(region)
            return np.array(cropped)
        except Exception as e:
            print(f'加载或裁剪图像时出错: {e}')
            return None

    def calculate_dhash(self, image_array):
        """
        计算图像的dHash值

        Args:
            image_array: 图像数组

        Returns:
            dHash字符串
        """
        try:
            # 转换为灰度图
            gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY) if len(image_array.shape) == 3 else image_array

            # 调整大小为 (hash_size + 1) x hash_size
            resized = cv2.resize(gray, (self.hash_size + 1, self.hash_size))

            # 计算水平梯度差异
            diff = resized[:, 1:] > resized[:, :-1]

            # 转换为哈希字符串
            return ''.join(['1' if pixel else '0' for row in diff for pixel in row])

        except Exception as e:
            print(f'计算dHash时出错: {e}')
            return None

    def hamming_distance(self, hash1, hash2):
        """
        计算两个哈希值的汉明距离

        Args:
            hash1: 第一个哈希值
            hash2: 第二个哈希值

        Returns:
            汉明距离
        """
        if len(hash1) != len(hash2):
            raise ValueError('哈希值长度不一致')

        return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))

    def compare_regions(self, image1_path, image2_path, region1, region2=None):
        """
        比较两个图像的指定区域

        Args:
            image1_path: 第一张图像路径
            image2_path: 第二张图像路径
            region1: 第一张图像的区域 (x1, y1, x2, y2)
            region2: 第二张图像的区域，如果为None则使用与region1相同的区域

        Returns:
            比较结果字典
        """
        if region2 is None:
            region2 = region1

        # 加载并裁剪区域
        region1_img = self.load_and_crop_region(image1_path, region1)
        region2_img = self.load_and_crop_region(image2_path, region2)

        if region1_img is None or region2_img is None:
            return None

        # 计算dHash
        hash1 = self.calculate_dhash(region1_img)
        hash2 = self.calculate_dhash(region2_img)

        if hash1 is None or hash2 is None:
            return None

        # 计算汉明距离
        distance = self.hamming_distance(hash1, hash2)

        # 计算相似度 (0-100)
        max_distance = len(hash1)
        similarity = (1 - distance / max_distance) * 100

        return {
            'hash1': hash1,
            'hash2': hash2,
            'hamming_distance': distance,
            'similarity_percentage': similarity,
            'region1_size': region1_img.shape,
            'region2_size': region2_img.shape,
        }

    def mark_regions_with_numbers(self, image_path, regions, output_path=None):
        """
        在图像上标记多个区域并用红框和编号标记

        Args:
            image_path: 输入图像路径
            regions: 区域列表，每个区域为 (x1, y1, x2, y2)
            output_path: 输出图像路径，如果为None则返回PIL图像对象

        Returns:
            PIL图像对象或保存路径
        """
        try:
            # 加载图像
            img = Image.open(image_path)
            img = img.convert('RGB')

            # 创建绘图对象
            draw = ImageDraw.Draw(img)

            # 尝试加载字体，如果失败则使用默认字体
            try:
                font = ImageFont.truetype('arial.ttf', 40)
            except OSError:
                try:
                    font = ImageFont.truetype('/System/Library/Fonts/Arial.ttf', 40)
                except OSError:
                    font = ImageFont.load_default()

            # 为每个区域绘制红框和编号
            for i, region in enumerate(regions):
                x1, y1, x2, y2 = region

                # 绘制红色矩形框
                draw.rectangle([x1, y1, x2, y2], outline='red', width=3)

                # 在区域左上角绘制编号
                text = str(i + 1)
                # 获取文本尺寸
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]

                # 绘制白色背景的文本
                text_x = x1 + 5
                text_y = y1 + 5
                draw.rectangle(
                    [text_x - 2, text_y - 2, text_x + text_width + 2, text_y + text_height + 2], fill='white'
                )
                draw.text((text_x, text_y), text, fill='red', font=font)

            if output_path:
                img.save(output_path)
                return output_path
            return img

        except Exception as e:
            print(f'标记区域时出错: {e}')
            return None

    def compare_multiple_regions(self, image1_path, image2_path, regions1, regions2=None):
        """
        比较两张图像的多个区域

        Args:
            image1_path: 第一张图像路径
            image2_path: 第二张图像路径
            regions1: 第一张图像的区域列表
            regions2: 第二张图像的区域列表，如果为None则使用与regions1相同的区域

        Returns:
            比较结果字典列表
        """
        if regions2 is None:
            regions2 = regions1

        if len(regions1) != len(regions2):
            print('警告: 两张图像的区域数量不一致')
            return None

        results = []

        for i, (region1, region2) in enumerate(zip(regions1, regions2)):
            print(f'正在比较区域 {i + 1}...')
            result = self.compare_regions(image1_path, image2_path, region1, region2)
            if result:
                result['region_index'] = i + 1
                result['region1'] = region1
                result['region2'] = region2
                results.append(result)
            else:
                print(f'区域 {i + 1} 比较失败')

        return results

    def generate_marked_images(
        self, image1_path, image2_path, regions1, regions2=None, output_dir='marked_images', file_name='marked_'
    ):
        """
        生成标记了区域的图像并保存

        Args:
            image1_path: 第一张图像路径
            image2_path: 第二张图像路径
            regions1: 第一张图像的区域列表
            regions2: 第二张图像的区域列表
            output_dir: 输出目录
            file_name：文件名

        Returns:
            标记后的图像路径列表
        """
        if regions2 is None:
            regions2 = regions1

        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

        # 生成标记后的图像
        marked_paths = []

        # 标记第一张图像
        marked_img1 = self.mark_regions_with_numbers(image1_path, regions1)
        if marked_img1:
            output_path1 = os.path.join(output_dir, f'{file_name}_1.png')
            marked_img1.save(output_path1)
            marked_paths.append(output_path1)
            print(f'已保存标记后的图像1: {output_path1}')

        # 标记第二张图像
        marked_img2 = self.mark_regions_with_numbers(image2_path, regions2)
        if marked_img2:
            output_path2 = os.path.join(output_dir, f'{file_name}_2.png')
            marked_img2.save(output_path2)
            marked_paths.append(output_path2)
            print(f'已保存标记后的图像2: {output_path2}')

        return marked_paths
