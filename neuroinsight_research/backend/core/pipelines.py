"""
Pipeline Plugin System

A flexible, YAML-based system for defining and managing neuroimaging pipelines.

DESIGN PHILOSOPHY:
- Pipeline-Agnostic: Easy integration of new analysis tools
- Declarative: YAML definitions separate configuration from code
- Type-Safe: Pydantic-like validation with dataclasses
- Versioned: Each pipeline tracks its version for reproducibility

YAML STRUCTURE:
    name: pipeline_name
    version: 1.0.0
    description: "..."
    container_image: docker/image
    inputs:
      - name: t1w
        type: nifti
        required: true
    parameters:
      - name: threads
        type: int
        default: 8
    resources:
      memory_gb: 32
      cpus: 8
      time_hours: 6
      gpu: false
    outputs:
      - name: segmentation
        path: segmentation.nii.gz
    command: "run_pipeline.sh"
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

logger = logging.getLogger(__name__)


class InputType(Enum):
    """Supported input file types for neuroimaging pipelines."""
    NIFTI = "nifti"
    DICOM = "dicom"
    TEXT = "text"
    JSON = "json"


class ParameterType(Enum):
    """Supported parameter types for pipeline configuration."""
    INT = "int"
    FLOAT = "float"
    STRING = "string"
    BOOL = "bool"
    CHOICE = "choice"


@dataclass
class InputSpec:
    """Specification for a pipeline input file."""
    name: str
    type: str = "nifti"
    required: bool = True
    description: str = ""


@dataclass
class ParameterSpec:
    """Specification for a configurable pipeline parameter."""
    name: str
    type: str = "string"
    default: Any = None
    description: str = ""
    choices: List[str] = field(default_factory=list)
    min_value: Optional[float] = None
    max_value: Optional[float] = None


@dataclass
class ResourceRequirements:
    """Default resource requirements for a pipeline."""
    memory_gb: int = 8
    cpus: int = 4
    time_hours: int = 6
    gpu: bool = False


@dataclass
class OutputSpec:
    """Specification for a pipeline output file."""
    name: str
    path: str = ""
    type: str = "nifti"
    description: str = ""


@dataclass
class PipelineDefinition:
    """Complete pipeline definition loaded from YAML."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    container_image: str = ""
    inputs: List[InputSpec] = field(default_factory=list)
    parameters: List[ParameterSpec] = field(default_factory=list)
    resources: ResourceRequirements = field(default_factory=ResourceRequirements)
    outputs: List[OutputSpec] = field(default_factory=list)
    command: str = ""
    authors: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)


class PipelineRegistry:
    """Registry for pipeline discovery and management.

    Implements the Plugin Pattern for neuroimaging pipelines.
    Pipelines are defined in YAML files and loaded dynamically at startup.
    """

    def __init__(self, pipelines_dir):
        """Initialize pipeline registry.

        Args:
            pipelines_dir: Directory containing pipeline YAML files
        """
        self.pipelines_dir = Path(pipelines_dir)
        self.pipelines: Dict[str, PipelineDefinition] = {}
        if self.pipelines_dir.exists():
            self._load_pipelines()
            logger.info(f"Pipeline registry initialized with {len(self.pipelines)} pipelines")
        else:
            logger.warning(
                f"Pipelines directory not found: {pipelines_dir}. "
                "No pipelines will be available. Create directory and add YAML files."
            )

    def _load_pipelines(self) -> None:
        """Scan directory and load all pipeline YAML files."""
        yaml_files = list(self.pipelines_dir.glob("*.yaml")) + list(self.pipelines_dir.glob("*.yml"))
        if not yaml_files:
            logger.warning(f"No pipeline YAML files found in {self.pipelines_dir}")
            return
        logger.info(f"Found {len(yaml_files)} pipeline definition files")
        loaded_count = 0
        failed_count = 0
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, "r") as f:
                    data = yaml.safe_load(f)
                if not data or not isinstance(data, dict):
                    logger.warning(f"Empty or invalid YAML: {yaml_file}")
                    failed_count += 1
                    continue

                name = data.get("name", yaml_file.stem)

                # Parse inputs
                inputs = []
                for inp in data.get("inputs", []):
                    if isinstance(inp, dict):
                        inputs.append(InputSpec(
                            name=inp.get("name", ""),
                            type=inp.get("type", "nifti"),
                            required=inp.get("required", True),
                            description=inp.get("description", ""),
                        ))

                # Parse parameters
                parameters = []
                for param in data.get("parameters", []):
                    if isinstance(param, dict):
                        parameters.append(ParameterSpec(
                            name=param.get("name", ""),
                            type=param.get("type", "string"),
                            default=param.get("default"),
                            description=param.get("description", ""),
                            choices=param.get("choices", []),
                            min_value=param.get("min_value"),
                            max_value=param.get("max_value"),
                        ))

                # Parse resources
                res_data = data.get("resources", {})
                resources = ResourceRequirements(
                    memory_gb=res_data.get("memory_gb", 8),
                    cpus=res_data.get("cpus", 4),
                    time_hours=res_data.get("time_hours", 6),
                    gpu=res_data.get("gpu", False),
                )

                # Parse outputs
                outputs = []
                for out in data.get("outputs", []):
                    if isinstance(out, dict):
                        outputs.append(OutputSpec(
                            name=out.get("name", ""),
                            path=out.get("path", ""),
                            type=out.get("type", "nifti"),
                            description=out.get("description", ""),
                        ))

                pipeline = PipelineDefinition(
                    name=name,
                    version=data.get("version", "1.0.0"),
                    description=data.get("description", ""),
                    container_image=data.get("container_image", ""),
                    inputs=inputs,
                    parameters=parameters,
                    resources=resources,
                    outputs=outputs,
                    command=data.get("command", ""),
                    authors=data.get("authors", []),
                    references=data.get("references", []),
                )
                self.pipelines[name] = pipeline
                loaded_count += 1
            except Exception as e:
                logger.error(f"Failed to load pipeline from {yaml_file}: {e}")
                failed_count += 1

        logger.info(f"Loaded {loaded_count} pipelines ({failed_count} failed)")

    def get_pipeline(self, name: str) -> Optional[PipelineDefinition]:
        """Get pipeline definition by name."""
        return self.pipelines.get(name)

    def list_pipelines(self) -> List[PipelineDefinition]:
        """List all available pipelines."""
        return list(self.pipelines.values())

    def has_pipeline(self, name: str) -> bool:
        """Check if pipeline exists in registry."""
        return name in self.pipelines

    def get_pipeline_names(self) -> List[str]:
        """Get sorted list of all pipeline names."""
        return sorted(self.pipelines.keys())

    def search_pipelines(self, query: str) -> List[PipelineDefinition]:
        """Search pipelines by name or description (case-insensitive)."""
        query_lower = query.lower()
        matches = []
        for pipeline in self.pipelines.values():
            if query_lower in pipeline.name.lower() or query_lower in pipeline.description.lower():
                matches.append(pipeline)
        return matches

    def reload(self) -> None:
        """Reload all pipeline definitions from disk."""
        logger.info("Reloading pipeline registry...")
        self.pipelines.clear()
        self._load_pipelines()

    def validate_all(self) -> Dict[str, List[str]]:
        """Validate all loaded pipelines.

        Returns:
            Dictionary mapping pipeline names to validation errors.
        """
        validation_errors: Dict[str, List[str]] = {}
        for name, pipeline in self.pipelines.items():
            errors = []
            if not pipeline.container_image:
                errors.append("Missing container_image")
            if not pipeline.inputs:
                errors.append("No inputs defined")
            if errors:
                validation_errors[name] = errors
        return validation_errors

    def __len__(self) -> int:
        return len(self.pipelines)

    def __repr__(self) -> str:
        return f"PipelineRegistry({len(self.pipelines)} pipelines)"


_registry: Optional[PipelineRegistry] = None


def get_pipeline_registry(pipelines_dir=None) -> PipelineRegistry:
    """Get global pipeline registry instance (singleton)."""
    global _registry
    if _registry is None:
        if pipelines_dir is None:
            pipelines_dir = Path(__file__).parent.parent.parent / "pipelines"
        _registry = PipelineRegistry(pipelines_dir)
    return _registry
