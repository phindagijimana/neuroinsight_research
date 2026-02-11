
'''
Plugin & Workflow Registry

Loads and manages plugins and workflows from YAML def initions.
Plugins are single-tool execution units; workflows are curated sequences.

Key design:
- Plugins define execution (container, command, inputs, outputs)
- Workflows define scientific intent (step ordering, dependency wiring)
- Hidden utility plugins (user_selectable=false) are only used by workflows
- All computation is in plugins; workflows only orchestrate
'''
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml
logger = logging.getLogger(__name__)
# NOTE: PluginDefinition dataclass def inition (decompiler artifact - see original)
# NOTE: WorkflowStep dataclass def inition (decompiler artifact - see original)
# NOTE: WorkflowDefinition dataclass def inition (decompiler artifact - see original)

class PluginWorkflowRegistry:
    '''
    Registry that loads and manages plugins and workflows.
    
    Usage:
        registry = PluginWorkflowRegistry(
            plugins_dir=Path("plugins"),
            workflows_dir=Path("workflows")
        )
        plugin = registry.get_plugin("fastsurfer")
        workflow = registry.get_workflow("structural_segmentation")
    '''
    
    def __init__(self = None, plugins_dir = None, workflows_dir = None):
        self.plugins_dir = Path(plugins_dir)
        self.workflows_dir = Path(workflows_dir)
        self.plugins = { }
        self.workflows = { }
        self._load_plugins()
        self._load_workflows()
        self._validate_workflows()
        logger.info(f"PluginWorkflowRegistry initialized: {len(self.plugins)} plugins, {len(self.workflows)} workflows")

    
    def _load_plugins(self = None):
        '''Load all plugin YAMLs from plugins directory.'''
        if not self.plugins_dir.exists():
            logger.warning(f"Plugins directory not found: {self.plugins_dir}")
            return None
        yaml_files = None(self.plugins_dir.glob('*.yaml')) + list(self.plugins_dir.glob('*.yml'))
    # WARNING: Decompyle incomplete

    
    def _load_workflows(self = None):
        '''Load all workflow YAMLs from workflows directory.'''
        if not self.workflows_dir.exists():
            logger.warning(f"Workflows directory not found: {self.workflows_dir}")
            return None
        yaml_files = None(self.workflows_dir.glob('*.yaml')) + list(self.workflows_dir.glob('*.yml'))
    # WARNING: Decompyle incomplete

    
    def _validate_workflows(self = None):
        '''Validate that all workflow steps reference existing plugins.'''
        for wf_id, workflow in self.workflows.items():
            for step in workflow.steps:
                if step.uses not in self.plugins:
                    logger.warning(f'''Workflow \'{wf_id}\' step \'{step.id}\' references unknown plugin \'{step.uses}\'''')

    
    def get_plugin(self = None, plugin_id = None):
        return self.plugins.get(plugin_id)

    
    def list_plugins(self = None, user_selectable_only = None):
        plugins = list(self.plugins.values())
        if user_selectable_only:
            plugins = [ p for p in plugins if p.user_selectable ]
        return plugins

    
    def get_plugin_ids(self = None):
        return sorted(self.plugins.keys())

    
    def get_workflow(self = None, workflow_id = None):
        return self.workflows.get(workflow_id)

    
    def list_workflows(self = None):
        return list(self.workflows.values())

    
    def get_workflow_ids(self = None):
        return sorted(self.workflows.keys())

    
    def reload(self = None):
        '''Reload all plugins and workflows from disk.'''
        logger.info('Reloading plugin/workflow registry...')
        self.plugins.clear()
        self.workflows.clear()
        self._load_plugins()
        self._load_workflows()
        self._validate_workflows()

    
    def __repr__(self = None):
        return f"PluginWorkflowRegistry({len(self.plugins)} plugins, {len(self.workflows)} workflows)"


_pw_registry: Optional[PluginWorkflowRegistry] = None

def get_plugin_workflow_registry(plugins_dir = None, workflows_dir = None):
    '''
    Get global plugin/workflow registry instance.
    
    First call must provide directories. Subsequent calls return cached instance.
    '''
    global _pw_registry
    if _pw_registry is None:
        if plugins_dir is None:
            plugins_dir = Path(__file__).parent.parent.parent / 'plugins'
        if workflows_dir is None:
            workflows_dir = Path(__file__).parent.parent.parent / 'workflows'
        _pw_registry = PluginWorkflowRegistry(plugins_dir, workflows_dir)
    return _pw_registry

