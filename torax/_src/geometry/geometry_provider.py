# Copyright 2024 DeepMind Technologies Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""GeometryProvider interface and implementations.

NOTE: Time dependent providers currently live in `geometry.py` and match the
protocol defined here.
"""
from collections.abc import Mapping
import dataclasses
from typing import Protocol, Type

import chex
import jax
import numpy as np
from torax._src import interpolated_param
from torax._src import jax_utils
from torax._src.geometry import geometry
from torax._src.torax_pydantic import torax_pydantic
import typing_extensions

# Using invalid-name because we are using the same naming convention as the
# external physics implementations
# pylint: disable=invalid-name


class GeometryProvider(Protocol):
  """Returns the geometry to use during one time step of the simulation.

  A GeometryProvider is any callable (class or function) which takes the
  time of a time step and returns the Geometry for that
  time step. See `SimulationStepFn` for how this callable is used.

  This class is a typing.Protocol, meaning it defines an interface, but any
  function asking for a GeometryProvider as an argument can accept any function
  or class that implements this API without specifically extending this class.

  For instance, the following is an equivalent implementation of the
  ConstantGeometryProvider without actually creating a class, and equally valid.

  .. code-block:: python

    geo = circular_geometry.build_circular_geometry(...)
    constant_geo_provider = lambda t: geo

    def func_expecting_geo_provider(gp: GeometryProvider):
      ... # do something with the provider.

    func_expecting_geo_provider(constant_geo_provider)  # this works.

  NOTE: In order to maintain consistency between the DynamicRuntimeParamsSlice
  and the geometry,
  `build_runtime_params.get_consistent_dynamic_runtime_params_slice_and_geometry`
  should be used to get a Geometry and a corresponding
  DynamicRuntimeParamsSlice.
  """

  def __call__(
      self,
      t: chex.Numeric,
  ) -> geometry.Geometry:
    """Returns the geometry to use during one time step of the simulation.

    The geometry may change from time step to time step, so the sim needs a
    callable to provide which geometry to use for a given time step (this is
    that callable).

    Args:
      t: The time at which the geometry is being requested.

    Returns:
      Geometry of the torus to use for the time step.
    """

  @property
  def torax_mesh(self) -> torax_pydantic.Grid1D:
    """Returns the mesh used by Torax, this is consistent across time."""


@jax.tree_util.register_dataclass
@dataclasses.dataclass(frozen=True)
class ConstantGeometryProvider(GeometryProvider):
  """Returns the same Geometry for all calls."""
  geo: geometry.Geometry

  def __call__(self, t: chex.Numeric) -> geometry.Geometry:
    # The API includes time as an arg even though it is unused in order
    # to match the API of a GeometryProvider.
    del t  # Ignored.
    return self.geo

  @property
  def torax_mesh(self) -> torax_pydantic.Grid1D:
    return self.geo.torax_mesh


@jax.tree_util.register_dataclass
@dataclasses.dataclass(frozen=True)
class TimeDependentGeometryProvider:
  """A geometry provider which holds values to interpolate based on time."""

  geometry_type: geometry.GeometryType
  torax_mesh: torax_pydantic.Grid1D
  drho_norm: interpolated_param.InterpolatedVarSingleAxis
  Phi: interpolated_param.InterpolatedVarSingleAxis
  Phi_face: interpolated_param.InterpolatedVarSingleAxis
  R_major: interpolated_param.InterpolatedVarSingleAxis
  a_minor: interpolated_param.InterpolatedVarSingleAxis
  B_0: interpolated_param.InterpolatedVarSingleAxis
  volume: interpolated_param.InterpolatedVarSingleAxis
  volume_face: interpolated_param.InterpolatedVarSingleAxis
  area: interpolated_param.InterpolatedVarSingleAxis
  area_face: interpolated_param.InterpolatedVarSingleAxis
  vpr: interpolated_param.InterpolatedVarSingleAxis
  vpr_face: interpolated_param.InterpolatedVarSingleAxis
  spr: interpolated_param.InterpolatedVarSingleAxis
  spr_face: interpolated_param.InterpolatedVarSingleAxis
  delta_face: interpolated_param.InterpolatedVarSingleAxis
  elongation: interpolated_param.InterpolatedVarSingleAxis
  elongation_face: interpolated_param.InterpolatedVarSingleAxis
  g0: interpolated_param.InterpolatedVarSingleAxis
  g0_face: interpolated_param.InterpolatedVarSingleAxis
  g1: interpolated_param.InterpolatedVarSingleAxis
  g1_face: interpolated_param.InterpolatedVarSingleAxis
  g2: interpolated_param.InterpolatedVarSingleAxis
  g2_face: interpolated_param.InterpolatedVarSingleAxis
  g3: interpolated_param.InterpolatedVarSingleAxis
  g3_face: interpolated_param.InterpolatedVarSingleAxis
  g2g3_over_rhon: interpolated_param.InterpolatedVarSingleAxis
  g2g3_over_rhon_face: interpolated_param.InterpolatedVarSingleAxis
  g2g3_over_rhon_hires: interpolated_param.InterpolatedVarSingleAxis
  F: interpolated_param.InterpolatedVarSingleAxis
  F_face: interpolated_param.InterpolatedVarSingleAxis
  F_hires: interpolated_param.InterpolatedVarSingleAxis
  R_in: interpolated_param.InterpolatedVarSingleAxis
  R_in_face: interpolated_param.InterpolatedVarSingleAxis
  R_out: interpolated_param.InterpolatedVarSingleAxis
  R_out_face: interpolated_param.InterpolatedVarSingleAxis
  spr_hires: interpolated_param.InterpolatedVarSingleAxis
  rho_hires_norm: interpolated_param.InterpolatedVarSingleAxis
  rho_hires: interpolated_param.InterpolatedVarSingleAxis
  _z_magnetic_axis: interpolated_param.InterpolatedVarSingleAxis | None

  @classmethod
  def create_provider(
      cls, geometries: Mapping[float, geometry.Geometry]
  ) -> typing_extensions.Self:
    """Creates a GeometryProvider from a mapping of times to geometries."""
    # Create a list of times and geometries.
    times = np.asarray(list(geometries.keys()), dtype=jax_utils.get_np_dtype())
    geos = list(geometries.values())
    initial_geometry = geos[0]
    for geo in geos:
      if geo.geometry_type != initial_geometry.geometry_type:
        raise ValueError('All geometries must have the same geometry type.')
      if geo.torax_mesh != initial_geometry.torax_mesh:
        raise ValueError('All geometries must have the same mesh.')
    # Create a list of interpolated parameters for each geometry attribute.
    kwargs = {
        'geometry_type': initial_geometry.geometry_type,
        'torax_mesh': initial_geometry.torax_mesh,
    }
    if hasattr(initial_geometry, 'Ip_from_parameters'):
      kwargs['Ip_from_parameters'] = initial_geometry.Ip_from_parameters
    for attr in dataclasses.fields(cls):
      if (
          attr.name == 'geometry_type'
          or attr.name == 'torax_mesh'
          or attr.name == 'Ip_from_parameters'
      ):
        continue
      if attr.name == '_z_magnetic_axis':
        if initial_geometry._z_magnetic_axis is None:  # pylint: disable=protected-access
          kwargs[attr.name] = None
          continue
      kwargs[attr.name] = interpolated_param.InterpolatedVarSingleAxis((
          times,
          np.stack(
              [getattr(g, attr.name) for g in geos],
              axis=0,
              dtype=jax_utils.get_np_dtype(),
          ),
      ))
    return cls(**kwargs)

  def _get_geometry_base(
      self, t: chex.Numeric, geometry_class: Type[geometry.Geometry]
  ):
    """Returns a Geometry instance of the given type at the given time."""
    kwargs = {
        'geometry_type': self.geometry_type,
        'torax_mesh': self.torax_mesh,
    }
    if hasattr(self, 'Ip_from_parameters'):
      kwargs['Ip_from_parameters'] = self.Ip_from_parameters
    for attr in dataclasses.fields(geometry_class):
      if (
          attr.name == 'geometry_type'
          or attr.name == 'torax_mesh'
          or attr.name == 'Ip_from_parameters'
      ):
        continue
      # always initialize Phibdot as zero. It will be replaced once both geo_t
      # and geo_t_plus_dt are provided, and set to be the same for geo_t and
      # geo_t_plus_dt for each given time interval.
      if attr.name == 'Phi_b_dot':
        kwargs[attr.name] = 0.0
        continue
      if attr.name == '_z_magnetic_axis':
        if self._z_magnetic_axis is None:
          kwargs[attr.name] = None
          continue
      kwargs[attr.name] = getattr(self, attr.name).get_value(t)
    return geometry_class(**kwargs)  # pytype: disable=wrong-keyword-args

  def __call__(self, t: chex.Numeric) -> geometry.Geometry:
    """Returns a Geometry instance at the given time."""
    return self._get_geometry_base(t, geometry.Geometry)
