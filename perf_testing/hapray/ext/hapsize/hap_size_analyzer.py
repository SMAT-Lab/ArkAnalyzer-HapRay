import hashlib
import json
import os
import zipfile
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class OptimizationImpact:
    """Impact of a specific optimization technique."""

    technique: str
    size_reduction_bytes: int
    size_reduction_percent: float
    file_count_affected: int
    estimated_download_time_saved: float
    estimated_storage_savings_mb: float
    confidence_level: str  # high, medium, low
    details: dict[str, Any]


@dataclass
class BusinessMetrics:
    """Business impact metrics."""

    download_time_improvement_seconds: float
    bandwidth_savings_mb: float
    storage_savings_mb: float
    estimated_cost_savings_usd: float
    user_experience_score: float  # 0-100
    deployment_speed_improvement_percent: float


@dataclass
class FileAnalysis:
    """Detailed file analysis with optimization potential."""

    path: str
    size: int
    compressed_size: int
    file_type: str
    category: str
    hash: str
    optimization_potential: list[str]
    compression_ratio: float
    is_optimizable: bool
    estimated_optimization_savings: int


@dataclass
class CategoryAnalysis:
    """Enhanced category analysis with optimization insights."""

    name: str
    total_size: int
    compressed_size: int
    file_count: int
    files: list[FileAnalysis]
    optimization_opportunities: list[OptimizationImpact]
    compression_efficiency: float
    largest_files: list[tuple[str, int]]
    duplicate_files: list[list[str]]


@dataclass
class HapAnalysis:
    """Enhanced HAP package analysis."""

    package_name: str
    package_path: str
    total_size: int
    compressed_size: int
    file_count: int
    categories: dict[str, CategoryAnalysis]
    files: list[FileAnalysis]
    analysis_time: str
    metadata: dict[str, Any]
    business_metrics: BusinessMetrics
    optimization_insights: list[OptimizationImpact]
    quality_score: float  # 0-100


class HapAnalyzer:
    """Enhanced HAP package analyzer with advanced features."""

    # Enhanced file type categories with optimization techniques
    FILE_CATEGORIES = {
        'images': {
            'extensions': ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg'],
            'optimization_techniques': ['webp_conversion', 'compression', 'resizing', 'progressive_loading'],
            'max_optimal_size_mb': 1.0,
        },
        'videos': {
            'extensions': ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm'],
            'optimization_techniques': ['codec_optimization', 'resolution_reduction', 'bitrate_optimization'],
            'max_optimal_size_mb': 10.0,
        },
        'audio': {
            'extensions': ['.mp3', '.wav', '.aac', '.ogg', '.flac'],
            'optimization_techniques': ['format_conversion', 'bitrate_reduction', 'stereo_to_mono'],
            'max_optimal_size_mb': 5.0,
        },
        'fonts': {
            'extensions': ['.ttf', '.otf', '.woff', '.woff2'],
            'optimization_techniques': ['subsetting', 'format_conversion', 'unicode_range_optimization'],
            'max_optimal_size_mb': 2.0,
        },
        'scripts': {
            'extensions': ['.js', '.ts', '.py', '.sh', '.bat'],
            'optimization_techniques': ['minification', 'tree_shaking', 'code_splitting'],
            'max_optimal_size_mb': 0.5,
        },
        'styles': {
            'extensions': ['.css', '.scss', '.less'],
            'optimization_techniques': ['minification', 'purge_unused', 'critical_css_extraction'],
            'max_optimal_size_mb': 0.2,
        },
        'binaries': {
            'extensions': ['.so', '.dll', '.dylib', '.exe'],
            'optimization_techniques': ['strip_debug_symbols', 'link_time_optimization', 'dead_code_elimination'],
            'max_optimal_size_mb': 5.0,
        },
        'bytecode': {
            'extensions': ['.abc'],
            'optimization_techniques': ['bytecode_optimization', 'dead_code_elimination'],
            'max_optimal_size_mb': 2.0,
        },
        'data': {
            'extensions': ['.json', '.xml', '.csv', '.yaml', '.yml'],
            'optimization_techniques': ['compression', 'format_optimization', 'data_cleaning'],
            'max_optimal_size_mb': 1.0,
        },
        'other': {'extensions': [], 'optimization_techniques': ['general_compression'], 'max_optimal_size_mb': 1.0},
    }

    def __init__(self):
        self.analysis_cache = {}
        self.optimization_techniques = {
            'webp_conversion': {'efficiency': 0.7, 'effort': 'medium'},
            'compression': {'efficiency': 0.5, 'effort': 'low'},
            'resizing': {'efficiency': 0.8, 'effort': 'high'},
            'minification': {'efficiency': 0.3, 'effort': 'low'},
            'strip_debug_symbols': {'efficiency': 0.4, 'effort': 'medium'},
            'subsetting': {'efficiency': 0.6, 'effort': 'medium'},
            'format_conversion': {'efficiency': 0.5, 'effort': 'medium'},
            'bytecode_optimization': {'efficiency': 0.2, 'effort': 'high'},
        }

    def analyze_hap(self, hap_path: str) -> HapAnalysis:
        """Analyze a HAP package with enhanced features."""
        hap_path = Path(hap_path)
        if not hap_path.exists():
            raise FileNotFoundError(f'HAP file not found: {hap_path}')

        # Check cache
        cache_key = f'{hap_path}_{hap_path.stat().st_mtime}'
        if cache_key in self.analysis_cache:
            return self.analysis_cache[cache_key]

        files = []
        categories = defaultdict(
            lambda: CategoryAnalysis(
                name='',
                total_size=0,
                compressed_size=0,
                file_count=0,
                files=[],
                optimization_opportunities=[],
                compression_efficiency=0.0,
                largest_files=[],
                duplicate_files=[],
            )
        )

        with zipfile.ZipFile(hap_path, 'r') as zf:
            for file_info in zf.infolist():
                if file_info.is_dir():
                    continue

                # Calculate file hash
                with zf.open(file_info.filename) as f:
                    content = f.read()
                    file_hash = hashlib.md5(content).hexdigest()

                # Enhanced file analysis
                file_ext = Path(file_info.filename).suffix.lower()
                file_type = self._get_file_type(file_ext)
                category = self._get_file_category(file_ext)
                compression_ratio = file_info.compress_size / file_info.file_size if file_info.file_size > 0 else 1.0

                # Analyze optimization potential
                optimization_potential = self._analyze_optimization_potential(
                    file_info.filename, file_ext, file_info.file_size, compression_ratio
                )

                file_analysis = FileAnalysis(
                    path=file_info.filename,
                    size=file_info.file_size,
                    compressed_size=file_info.compress_size,
                    file_type=file_type,
                    category=category,
                    hash=file_hash,
                    optimization_potential=optimization_potential,
                    compression_ratio=compression_ratio,
                    is_optimizable=len(optimization_potential) > 0,
                    estimated_optimization_savings=self._estimate_optimization_savings(
                        file_info.file_size, optimization_potential
                    ),
                )

                files.append(file_analysis)

                # Update category info
                if category not in categories:
                    categories[category] = CategoryAnalysis(
                        name=category,
                        total_size=0,
                        compressed_size=0,
                        file_count=0,
                        files=[],
                        optimization_opportunities=[],
                        compression_efficiency=0.0,
                        largest_files=[],
                        duplicate_files=[],
                    )

                categories[category].total_size += file_info.file_size
                categories[category].compressed_size += file_info.compress_size
                categories[category].file_count += 1
                categories[category].files.append(file_analysis)

        # Analyze categories for optimization opportunities
        for _category_name, category in categories.items():
            self._analyze_category_optimization(category)

        # Extract metadata
        metadata = self._extract_metadata(hap_path)

        # Calculate business metrics
        business_metrics = self._calculate_business_metrics(files, categories)

        # Generate optimization insights
        optimization_insights = self._generate_optimization_insights(categories)

        # Calculate quality score
        quality_score = self._calculate_quality_score(files, categories, business_metrics)

        analysis = HapAnalysis(
            package_name=hap_path.stem,
            package_path=str(hap_path),
            total_size=sum(f.size for f in files),
            compressed_size=sum(f.compressed_size for f in files),
            file_count=len(files),
            categories=dict(categories),
            files=files,
            analysis_time=datetime.now().isoformat(),
            metadata=metadata,
            business_metrics=business_metrics,
            optimization_insights=optimization_insights,
            quality_score=quality_score,
        )

        # Cache the result
        self.analysis_cache[cache_key] = analysis
        return analysis

    def _get_file_type(self, extension: str) -> str:
        """Get the file type based on extension."""
        return extension[1:] if extension else 'unknown'

    def _get_file_category(self, extension: str) -> str:
        """Categorize file based on extension."""
        for category, info in self.FILE_CATEGORIES.items():
            if extension in info['extensions']:
                return category
        return 'other'

    def _analyze_optimization_potential(
        self, filepath: str, extension: str, size: int, compression_ratio: float
    ) -> list[str]:
        """Analyze optimization potential for a file."""
        potential = []

        # Get category info
        category = self._get_file_category(extension)
        category_info = self.FILE_CATEGORIES[category]

        # Check if file is larger than optimal
        max_optimal_size = category_info['max_optimal_size_mb'] * 1024 * 1024
        if size > max_optimal_size:
            potential.extend(category_info['optimization_techniques'])

        # Check compression efficiency
        if compression_ratio > 0.9:  # Poor compression
            potential.append('compression')

        # Specific checks
        if extension in ['.png', '.jpg', '.jpeg'] and size > 500 * 1024:  # > 500KB
            potential.append('webp_conversion')

        if extension in ['.js', '.css'] and size > 100 * 1024:  # > 100KB
            potential.append('minification')

        if extension in ['.ttf', '.otf'] and size > 1 * 1024 * 1024:  # > 1MB
            potential.append('subsetting')

        if extension in ['.so', '.dll'] and size > 2 * 1024 * 1024:  # > 2MB
            potential.append('strip_debug_symbols')

        return list(set(potential))  # Remove duplicates

    def _estimate_optimization_savings(self, size: int, techniques: list[str]) -> int:
        """Estimate size savings from optimization techniques."""
        total_savings = 0
        for technique in techniques:
            if technique in self.optimization_techniques:
                efficiency = self.optimization_techniques[technique]['efficiency']
                total_savings += int(size * efficiency * 0.3)  # Conservative estimate
        return min(total_savings, size // 2)  # Cap at 50% of original size

    def _analyze_category_optimization(self, category: CategoryAnalysis):
        """Analyze optimization opportunities for a category."""
        if not category.files:
            return

        # Calculate compression efficiency
        category.compression_efficiency = (
            category.compressed_size / category.total_size if category.total_size > 0 else 1.0
        )

        # Find largest files
        largest_files = sorted(category.files, key=lambda f: f.size, reverse=True)[:5]
        category.largest_files = [(f.path, f.size) for f in largest_files]

        # Find duplicate files (same size and hash)
        hash_groups = defaultdict(list)
        for file in category.files:
            hash_groups[file.hash].append(file.path)

        category.duplicate_files = [paths for paths in hash_groups.values() if len(paths) > 1]

        # Generate optimization opportunities
        optimization_opportunities = []

        # Large files optimization
        large_files = [f for f in category.files if f.is_optimizable]
        if large_files:
            total_savings = sum(f.estimated_optimization_savings for f in large_files)
            optimization_opportunities.append(
                OptimizationImpact(
                    technique='large_file_optimization',
                    size_reduction_bytes=total_savings,
                    size_reduction_percent=(total_savings / category.total_size * 100)
                    if category.total_size > 0
                    else 0,
                    file_count_affected=len(large_files),
                    estimated_download_time_saved=total_savings / (1024 * 1024) * 2,  # Rough estimate
                    estimated_storage_savings_mb=total_savings / (1024 * 1024),
                    confidence_level='high',
                    details={'files': [f.path for f in large_files]},
                )
            )

        # Duplicate removal
        if category.duplicate_files:
            duplicate_savings = sum(
                sum(f.size for f in category.files if f.path in dup_group[1:]) for dup_group in category.duplicate_files
            )
            optimization_opportunities.append(
                OptimizationImpact(
                    technique='duplicate_removal',
                    size_reduction_bytes=duplicate_savings,
                    size_reduction_percent=(duplicate_savings / category.total_size * 100)
                    if category.total_size > 0
                    else 0,
                    file_count_affected=sum(len(dup_group) - 1 for dup_group in category.duplicate_files),
                    estimated_download_time_saved=duplicate_savings / (1024 * 1024) * 2,
                    estimated_storage_savings_mb=duplicate_savings / (1024 * 1024),
                    confidence_level='high',
                    details={'duplicate_groups': category.duplicate_files},
                )
            )

        category.optimization_opportunities = optimization_opportunities

    def _calculate_business_metrics(
        self, files: list[FileAnalysis], categories: dict[str, CategoryAnalysis]
    ) -> BusinessMetrics:
        """Calculate business impact metrics."""
        total_size = sum(f.size for f in files)
        total_optimization_savings = sum(f.estimated_optimization_savings for f in files)

        # Download time improvement (assuming 10 Mbps connection)
        download_speed_mbps = 10
        current_download_time = total_size / (download_speed_mbps * 1024 * 1024 / 8)
        optimized_download_time = (total_size - total_optimization_savings) / (download_speed_mbps * 1024 * 1024 / 8)
        download_time_improvement = current_download_time - optimized_download_time

        # Bandwidth savings
        bandwidth_savings = total_optimization_savings / (1024 * 1024)

        # Storage savings
        storage_savings = bandwidth_savings

        # Cost savings (rough estimate: $0.09 per GB)
        cost_per_gb = 0.09
        cost_savings = (bandwidth_savings / 1024) * cost_per_gb

        # User experience score (based on size, optimization potential, etc.)
        ux_score = max(0, 100 - (total_size / (1024 * 1024) * 2))  # Penalty for large size
        ux_score += min(20, total_optimization_savings / (1024 * 1024) * 10)  # Bonus for optimization potential

        # Deployment speed improvement
        deployment_improvement = (total_optimization_savings / total_size * 100) if total_size > 0 else 0

        return BusinessMetrics(
            download_time_improvement_seconds=download_time_improvement,
            bandwidth_savings_mb=bandwidth_savings,
            storage_savings_mb=storage_savings,
            estimated_cost_savings_usd=cost_savings,
            user_experience_score=min(100, max(0, ux_score)),
            deployment_speed_improvement_percent=deployment_improvement,
        )

    def _generate_optimization_insights(self, categories: dict[str, CategoryAnalysis]) -> list[OptimizationImpact]:
        """Generate overall optimization insights."""
        insights = []

        # Aggregate optimization opportunities across categories
        technique_savings = defaultdict(int)
        technique_files = defaultdict(int)

        for category in categories.values():
            for opportunity in category.optimization_opportunities:
                technique_savings[opportunity.technique] += opportunity.size_reduction_bytes
                technique_files[opportunity.technique] += opportunity.file_count_affected

        total_size = sum(cat.total_size for cat in categories.values())

        for technique, savings in technique_savings.items():
            insights.append(
                OptimizationImpact(
                    technique=technique,
                    size_reduction_bytes=savings,
                    size_reduction_percent=(savings / total_size * 100) if total_size > 0 else 0,
                    file_count_affected=technique_files[technique],
                    estimated_download_time_saved=savings / (1024 * 1024) * 2,
                    estimated_storage_savings_mb=savings / (1024 * 1024),
                    confidence_level='high' if technique_files[technique] > 0 else 'low',
                    details={
                        'affected_categories': [
                            cat.name
                            for cat in categories.values()
                            if any(opp.technique == technique for opp in cat.optimization_opportunities)
                        ]
                    },
                )
            )

        return insights

    def _calculate_quality_score(
        self, files: list[FileAnalysis], categories: dict[str, CategoryAnalysis], business_metrics: BusinessMetrics
    ) -> float:
        """Calculate overall package quality score (0-100)."""
        score = 100.0

        # Penalize large total size
        total_size_mb = sum(f.size for f in files) / (1024 * 1024)
        if total_size_mb > 50:
            score -= 20
        elif total_size_mb > 20:
            score -= 10

        # Penalize poor compression
        total_compressed = sum(f.compressed_size for f in files)
        total_uncompressed = sum(f.size for f in files)
        compression_ratio = total_compressed / total_uncompressed if total_uncompressed > 0 else 1.0
        if compression_ratio > 0.95:
            score -= 15

        # Penalize unoptimized files
        unoptimized_ratio = len([f for f in files if not f.is_optimizable]) / len(files) if files else 1.0
        score -= unoptimized_ratio * 20

        # Penalize duplicates
        total_duplicates = sum(len(dup_group) - 1 for cat in categories.values() for dup_group in cat.duplicate_files)
        if total_duplicates > 0:
            score -= min(15, total_duplicates * 2)

        # Bonus for good business metrics
        score += business_metrics.user_experience_score * 0.1

        return max(0, min(100, score))

    def _extract_metadata(self, hap_path: Path) -> dict[str, Any]:
        """Extract metadata from HAP package."""
        metadata = {}

        try:
            with zipfile.ZipFile(hap_path, 'r') as zf:
                # Try to read module.json
                if 'module.json' in zf.namelist():
                    with zf.open('module.json') as f:
                        try:
                            module_data = json.load(f)
                            metadata['module'] = module_data
                        except json.JSONDecodeError:
                            metadata['module'] = {'error': 'Invalid JSON'}

                # Try to read resources.index
                if 'resources.index' in zf.namelist():
                    with zf.open('resources.index') as f:
                        try:
                            resources_data = json.load(f)
                            metadata['resources'] = resources_data
                        except json.JSONDecodeError:
                            metadata['resources'] = {'error': 'Invalid JSON'}

                # Get basic package info
                metadata['package_info'] = {
                    'filename': hap_path.name,
                    'size_bytes': hap_path.stat().st_size,
                    'file_count': len([f for f in zf.namelist() if not f.endswith('/')]),
                }

        except Exception as e:
            metadata['error'] = str(e)

        return metadata

    def format_size(self, bytes_value: int) -> str:
        """Format bytes into human readable format."""
        if bytes_value == 0:
            return '0 B'

        size_names = ['B', 'KB', 'MB', 'GB']
        i = 0
        while bytes_value >= 1024 and i < len(size_names) - 1:
            bytes_value /= 1024.0
            i += 1

        return f'{bytes_value:.1f} {size_names[i]}'


class HapComparator:
    """Enhanced HAP package comparator with advanced analysis."""

    def __init__(self):
        self.analyzer = HapAnalyzer()

    def compare_haps(self, hap1_path: str, hap2_path: str) -> dict[str, Any]:
        """Compare two HAP packages with enhanced analysis."""
        analysis1 = self.analyzer.analyze_hap(hap1_path)
        analysis2 = self.analyzer.analyze_hap(hap2_path)

        return {
            'hap1': asdict(analysis1),
            'hap2': asdict(analysis2),
            'comparison': self._generate_comparison(analysis1, analysis2),
            'summary': self._generate_summary(analysis1, analysis2),
            'file_differences': self._analyze_file_differences(analysis1, analysis2),
            'category_differences': self._analyze_category_differences(analysis1, analysis2),
            'optimization_impact': self._analyze_optimization_impact(analysis1, analysis2),
            'business_impact': self._analyze_business_impact(analysis1, analysis2),
            'recommendations': self._generate_recommendations(analysis1, analysis2),
            'comparison_time': datetime.now().isoformat(),
        }

    def _generate_comparison(self, hap1: HapAnalysis, hap2: HapAnalysis) -> dict[str, Any]:
        """Generate detailed comparison between two HAPs."""
        size_diff = hap2.total_size - hap1.total_size
        size_diff_percent = (size_diff / hap1.total_size * 100) if hap1.total_size > 0 else 0

        compressed_diff = hap2.compressed_size - hap1.compressed_size
        compressed_diff_percent = (compressed_diff / hap1.compressed_size * 100) if hap1.compressed_size > 0 else 0

        file_count_diff = hap2.file_count - hap1.file_count
        quality_score_diff = hap2.quality_score - hap1.quality_score

        return {
            'size_difference': {
                'bytes': size_diff,
                'percent': size_diff_percent,
                'formatted': self.analyzer.format_size(size_diff),
            },
            'compressed_size_difference': {
                'bytes': compressed_diff,
                'percent': compressed_diff_percent,
                'formatted': self.analyzer.format_size(compressed_diff),
            },
            'file_count_difference': file_count_diff,
            'quality_score_difference': quality_score_diff,
            'compression_ratio_change': {
                'hap1': hap1.compressed_size / hap1.total_size if hap1.total_size > 0 else 0,
                'hap2': hap2.compressed_size / hap2.total_size if hap2.total_size > 0 else 0,
            },
        }

    def _generate_summary(self, hap1: HapAnalysis, hap2: HapAnalysis) -> dict[str, Any]:
        """Generate executive summary."""
        comparison = self._generate_comparison(hap1, hap2)

        # Determine if it's an improvement
        size_improvement = comparison['size_difference']['bytes'] < 0
        quality_improvement = comparison['quality_score_difference'] > 0

        return {
            'overall_assessment': 'IMPROVEMENT' if size_improvement and quality_improvement else 'INCREASE',
            'size_change': comparison['size_difference'],
            'quality_change': comparison['quality_score_difference'],
            'business_impact': self._analyze_business_impact(hap1, hap2),
            'key_insights': self._generate_key_insights(hap1, hap2, comparison),
        }

    def _analyze_optimization_impact(self, hap1: HapAnalysis, hap2: HapAnalysis) -> dict[str, Any]:
        """Analyze optimization impact between versions."""
        return {
            'hap1_optimization_potential': {
                'total_savings': sum(f.estimated_optimization_savings for f in hap1.files),
                'techniques': [insight.technique for insight in hap1.optimization_insights],
                'file_count': len([f for f in hap1.files if f.is_optimizable]),
            },
            'hap2_optimization_potential': {
                'total_savings': sum(f.estimated_optimization_savings for f in hap2.files),
                'techniques': [insight.technique for insight in hap2.optimization_insights],
                'file_count': len([f for f in hap2.files if f.is_optimizable]),
            },
            'improvement': {
                'savings_reduction': sum(f.estimated_optimization_savings for f in hap1.files)
                - sum(f.estimated_optimization_savings for f in hap2.files),
                'techniques_applied': self._identify_applied_techniques(hap1, hap2),
            },
        }

    def _analyze_business_impact(self, hap1: HapAnalysis, hap2: HapAnalysis) -> dict[str, Any]:
        """Analyze business impact of changes."""
        download_time_diff = (
            hap2.business_metrics.download_time_improvement_seconds
            - hap1.business_metrics.download_time_improvement_seconds
        )
        bandwidth_diff = hap2.business_metrics.bandwidth_savings_mb - hap1.business_metrics.bandwidth_savings_mb
        cost_diff = hap2.business_metrics.estimated_cost_savings_usd - hap1.business_metrics.estimated_cost_savings_usd
        ux_diff = hap2.business_metrics.user_experience_score - hap1.business_metrics.user_experience_score

        return {
            'download_time_improvement': download_time_diff,
            'bandwidth_savings': bandwidth_diff,
            'cost_savings': cost_diff,
            'user_experience_improvement': ux_diff,
            'roi_improvement': self._calculate_roi_improvement(hap1, hap2),
        }

    def _identify_applied_techniques(self, hap1: HapAnalysis, hap2: HapAnalysis) -> list[str]:
        """Identify optimization techniques that were applied between versions."""
        # This is a simplified implementation - in practice, you'd need more sophisticated analysis
        applied_techniques = []

        # Compare file types and sizes to infer applied techniques
        hap1_large_images = [f for f in hap1.files if f.category == 'images' and f.size > 500 * 1024]
        hap2_large_images = [f for f in hap2.files if f.category == 'images' and f.size > 500 * 1024]

        if len(hap1_large_images) > len(hap2_large_images):
            applied_techniques.append('image_optimization')

        # Check for webp conversion
        hap1_webp_count = len([f for f in hap1.files if f.path.endswith('.webp')])
        hap2_webp_count = len([f for f in hap2.files if f.path.endswith('.webp')])

        if hap2_webp_count > hap1_webp_count:
            applied_techniques.append('webp_conversion')

        return applied_techniques

    def _calculate_roi_improvement(self, hap1: HapAnalysis, hap2: HapAnalysis) -> float:
        """Calculate ROI improvement from optimization."""
        # Simplified ROI calculation
        hap1_optimization_cost = sum(f.estimated_optimization_savings for f in hap1.files) * 0.001  # Cost per byte
        hap2_optimization_cost = sum(f.estimated_optimization_savings for f in hap2.files) * 0.001

        hap1_benefit = hap1.business_metrics.estimated_cost_savings_usd
        hap2_benefit = hap2.business_metrics.estimated_cost_savings_usd

        roi1 = (hap1_benefit - hap1_optimization_cost) / hap1_optimization_cost if hap1_optimization_cost > 0 else 0
        roi2 = (hap2_benefit - hap2_optimization_cost) / hap2_optimization_cost if hap2_optimization_cost > 0 else 0

        return roi2 - roi1

    def _generate_key_insights(self, hap1: HapAnalysis, hap2: HapAnalysis, comparison: dict) -> list[str]:
        """Generate key insights for the summary."""
        insights = []

        # Overall size change
        if comparison['size_difference']['bytes'] < 0:
            insights.append(
                f'🎉 Package size reduced by {self.analyzer.format_size(abs(comparison["size_difference"]["bytes"]))} ({abs(comparison["size_difference"]["percent"]):.1f}%)'
            )
        else:
            insights.append(
                f'📈 Package size increased by {comparison["size_difference"]["formatted"]} ({comparison["size_difference"]["percent"]:.1f}%)'
            )

        # Quality score change
        if comparison['quality_score_difference'] > 0:
            insights.append(f'⭐ Quality score improved by {comparison["quality_score_difference"]:.1f} points')
        elif comparison['quality_score_difference'] < 0:
            insights.append(f'⚠️ Quality score decreased by {abs(comparison["quality_score_difference"]):.1f} points')

        # Business impact
        business_impact = self._analyze_business_impact(hap1, hap2)
        if business_impact['download_time_improvement'] > 0:
            insights.append(f'⚡ Download time improved by {business_impact["download_time_improvement"]:.1f} seconds')

        if business_impact['cost_savings'] > 0:
            insights.append(f'💰 Estimated cost savings: ${business_impact["cost_savings"]:.2f}')

        return insights

    def _analyze_file_differences(self, hap1: HapAnalysis, hap2: HapAnalysis) -> dict[str, Any]:
        """Analyze differences at file level."""
        hap1_files = {f.path: f for f in hap1.files}
        hap2_files = {f.path: f for f in hap2.files}

        added_files = []
        removed_files = []
        modified_files = []

        # Find added files
        for path, file_info in hap2_files.items():
            if path not in hap1_files:
                added_files.append(
                    {
                        'path': path,
                        'size': file_info.size,
                        'category': file_info.category,
                        'file_type': file_info.file_type,
                        'optimization_potential': file_info.optimization_potential,
                        'estimated_savings': file_info.estimated_optimization_savings,
                    }
                )

        # Find removed files
        for path, file_info in hap1_files.items():
            if path not in hap2_files:
                removed_files.append(
                    {
                        'path': path,
                        'size': file_info.size,
                        'category': file_info.category,
                        'file_type': file_info.file_type,
                        'optimization_potential': file_info.optimization_potential,
                        'estimated_savings': file_info.estimated_optimization_savings,
                    }
                )

        # Find modified files
        for path, file2_info in hap2_files.items():
            if path in hap1_files:
                file1_info = hap1_files[path]
                if file1_info.hash != file2_info.hash:
                    modified_files.append(
                        {
                            'path': path,
                            'size_change': file2_info.size - file1_info.size,
                            'size_change_percent': ((file2_info.size - file1_info.size) / file1_info.size * 100)
                            if file1_info.size > 0
                            else 0,
                            'category': file2_info.category,
                            'file_type': file2_info.file_type,
                            'optimization_improvement': len(file2_info.optimization_potential)
                            < len(file1_info.optimization_potential),
                        }
                    )

        return {
            'added_files': added_files,
            'removed_files': removed_files,
            'modified_files': modified_files,
            'summary': {
                'added_count': len(added_files),
                'removed_count': len(removed_files),
                'modified_count': len(modified_files),
                'added_size': sum(f['size'] for f in added_files),
                'removed_size': sum(f['size'] for f in removed_files),
                'modified_size_change': sum(f['size_change'] for f in modified_files),
                'total_optimization_potential': sum(f['estimated_savings'] for f in added_files),
            },
        }

    def _analyze_category_differences(self, hap1: HapAnalysis, hap2: HapAnalysis) -> dict[str, Any]:
        """Analyze differences at category level."""
        all_categories = set(hap1.categories.keys()) | set(hap2.categories.keys())
        category_diffs = {}

        for category in all_categories:
            cat1 = hap1.categories.get(category)
            cat2 = hap2.categories.get(category)

            if cat1 and cat2:
                # Both exist, compare
                size_diff = cat2.total_size - cat1.total_size
                size_diff_percent = (size_diff / cat1.total_size * 100) if cat1.total_size > 0 else 0

                category_diffs[category] = {
                    'type': 'modified',
                    'size_difference': {
                        'bytes': size_diff,
                        'percent': size_diff_percent,
                        'formatted': self.analyzer.format_size(size_diff),
                    },
                    'file_count_difference': cat2.file_count - cat1.file_count,
                    'hap1_size': cat1.total_size,
                    'hap2_size': cat2.total_size,
                    'optimization_improvement': len(cat2.optimization_opportunities)
                    < len(cat1.optimization_opportunities),
                }
            elif cat1:
                # Only in hap1 (removed)
                category_diffs[category] = {'type': 'removed', 'size': cat1.total_size, 'file_count': cat1.file_count}
            else:
                # Only in hap2 (added)
                category_diffs[category] = {'type': 'added', 'size': cat2.total_size, 'file_count': cat2.file_count}

        return category_diffs

    def _generate_recommendations(self, hap1: HapAnalysis, hap2: HapAnalysis) -> list[str]:
        """Generate recommendations for size optimization."""
        recommendations = []
        comparison = self._generate_comparison(hap1, hap2)

        # Size increase recommendations
        if comparison['size_difference']['bytes'] > 0:
            recommendations.append(
                f'⚠️ Package size increased by {comparison["size_difference"]["formatted"]} ({comparison["size_difference"]["percent"]:.1f}%)'
            )

            # Analyze largest increases
            file_diffs = self._analyze_file_differences(hap1, hap2)
            if file_diffs['added_files']:
                largest_added = max(file_diffs['added_files'], key=lambda x: x['size'])
                recommendations.append(
                    f'📁 Largest added file: {largest_added["path"]} ({self.analyzer.format_size(largest_added["size"])})'
                )

                if largest_added['optimization_potential']:
                    recommendations.append(
                        f'🔧 Optimization potential: {", ".join(largest_added["optimization_potential"])}'
                    )

        # Quality score recommendations
        if comparison['quality_score_difference'] < 0:
            recommendations.append(
                f'📊 Quality score decreased by {abs(comparison["quality_score_difference"]):.1f} points - review optimization opportunities'
            )

        # Business impact recommendations
        business_impact = self._analyze_business_impact(hap1, hap2)
        if business_impact['download_time_improvement'] < 0:
            recommendations.append('⏱️ Download time increased - consider implementing aggressive optimization')

        if business_impact['cost_savings'] < 0:
            recommendations.append('💸 Cost impact increased - prioritize high-impact optimizations')

        # Specific optimization recommendations
        optimization_impact = self._analyze_optimization_impact(hap1, hap2)
        if optimization_impact['improvement']['savings_reduction'] < 0:
            recommendations.append(
                f'🎯 Optimization potential reduced by {self.analyzer.format_size(abs(optimization_impact["improvement"]["savings_reduction"]))} - good progress!'
            )

        return recommendations


if __name__ == '__main__':
    # Test the enhanced analyzer
    analyzer = HapAnalyzer()
    comparator = HapComparator()

    # Test with sample HAP files
    hap_files = [
        'D:/code/binary_insight_framework/shared/hap_packages/packages/Legado-20250521-V1.0.1.2-unsigned.hap',
        'D:/code/binary_insight_framework/shared/hap_packages/packages/ClashNEXT-1.3.3.hap',
    ]

    for hap_file in hap_files:
        if os.path.exists(hap_file):
            print(f'\nAnalyzing {hap_file}...')
            analysis = analyzer.analyze_hap(hap_file)
            print(f'Package: {analysis.package_name}')
            print(f'Total size: {analyzer.format_size(analysis.total_size)}')
            print(f'Quality score: {analysis.quality_score:.1f}/100')
            print(
                f'Optimization potential: {analyzer.format_size(sum(f.estimated_optimization_savings for f in analysis.files))}'
            )
            print(f'Business impact: ${analysis.business_metrics.estimated_cost_savings_usd:.2f} potential savings')

    print(comparator.compare_haps(hap_files[0], hap_files[1]))
