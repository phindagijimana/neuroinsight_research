
'''
Execution Backend Module

Factory for creating execution backends based on configuration.
'''
import os
from typing import Optional
from backend.core.execution import ExecutionBackend, BackendUnavailableError
from backend.execution.local_backend import LocalDockerBackend
from backend.execution.slurm_backend import SLURMBackend

def create_backend(backend_type = None, **kwargs):
    """
    Factory function to create appropriate execution backend.
    
    Args:
        backend_type: Backend type ('local', 'slurm'). 
                     If None, reads from BACKEND_TYPE env var.
        **kwargs: Backend-specific configuration
        
    Returns:
        ExecutionBackend instance
        
    Raises:
        ValueError: If backend_type is unknown
        BackendUnavailableError: If backend cannot be initialized
        
    Example:
        # Local development
        backend = create_backend('local', data_dir='/data')
        
        # HPC production (Phase 2)
        backend = create_backend('slurm', 
                                ssh_host='hpc.university.edu',
                                ssh_user='researcher')
    """
    if backend_type is None:
        backend_type = os.getenv('BACKEND_TYPE', 'local')
    backend_type = backend_type.lower().strip()
    if backend_type == 'local' or backend_type == 'local_docker':
        data_dir = kwargs.get('data_dir', os.getenv('DATA_DIR', './data'))
        max_concurrent_jobs = int(kwargs.get('max_concurrent_jobs', os.getenv('MAX_CONCURRENT_JOBS', 2)))
        return LocalDockerBackend(data_dir, max_concurrent_jobs, **('data_dir', 'max_concurrent_jobs'))
    if None == 'slurm':
        ssh_host = kwargs.get('ssh_host', os.getenv('HPC_HOST'))
        ssh_user = kwargs.get('ssh_user', os.getenv('HPC_USER'))
        work_dir = kwargs.get('work_dir', os.getenv('HPC_WORK_DIR', '/scratch'))
        partition = kwargs.get('partition', os.getenv('HPC_PARTITION', 'general'))
        if not ssh_host or ssh_user:
            raise ValueError('SLURM backend requires ssh_host and ssh_user. Set HPC_HOST and HPC_USER environment variables.')
        return SLURMBackend(ssh_host, ssh_user, work_dir, partition, **('ssh_host', 'ssh_user', 'work_dir', 'partition'))
    raise None(f'''Unknown backend type: {backend_type}. Supported: \'local\', \'slurm\'''')

_backend_instance: Optional[ExecutionBackend] = None

def get_backend(reinit = None):
    '''
    Get singleton execution backend instance.
    
    Args:
        reinit: Force reinitialization of backend
        
    Returns:
        ExecutionBackend instance
    '''
    global _backend_instance
    if _backend_instance is None or reinit:
        _backend_instance = create_backend()
    return _backend_instance

__all__ = [
    'ExecutionBackend',
    'LocalDockerBackend',
    'SLURMBackend',
    'create_backend',
    'get_backend']
