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

"""Pydantic utilities and base classes."""

from collections.abc import Mapping
from typing import Annotated, Any, TypeAlias
import numpy as np
import pydantic
from typing_extensions import Self

DataTypes: TypeAlias = float | int | bool

DtypeName: TypeAlias = str


NestedList: TypeAlias = (
    DataTypes
    | list[DataTypes]
    | list[list[DataTypes]]
    | list[list[list[DataTypes]]]
)

NumpySerialized: TypeAlias = tuple[DtypeName, NestedList]


def _numpy_array_before_validator(
    x: np.ndarray | NumpySerialized,
) -> np.ndarray:

  if isinstance(x, np.ndarray):
    return x
  else:
    dtype, data = x
    return np.array(data, dtype=np.dtype(dtype))


def _numpy_array_serializer(x: np.ndarray) -> NumpySerialized:
  return (x.dtype.name, x.tolist())


def _numpy_array_is_rank_1(x: np.ndarray) -> np.ndarray:
  if x.ndim != 1:
    raise ValueError(f'NumPy array is not 1D, rather of rank {x.ndim}')
  return x


NumpyArray = Annotated[
    np.ndarray,
    pydantic.BeforeValidator(_numpy_array_before_validator),
    pydantic.PlainSerializer(
        _numpy_array_serializer, return_type=NumpySerialized
    ),
]

NumpyArray1D = Annotated[
    NumpyArray, pydantic.AfterValidator(_numpy_array_is_rank_1)
]


class Base(pydantic.BaseModel):
  """Base config class. Any custom config classes should inherit from this.

  See https://docs.pydantic.dev/latest/ for documentation on pydantic.
  """

  model_config = pydantic.ConfigDict(
      frozen=False,
      # Do not allow attributes not defined in pydantic model.
      extra='forbid',
      # Re-run validation if the model is updated.
      validate_assignment=True,
      arbitrary_types_allowed=True,
  )

  @classmethod
  def from_dict(cls: type[Self], cfg: Mapping[str, Any]) -> Self:
    return cls.model_validate(cfg)

  def to_dict(self) -> dict[str, Any]:
    return self.model_dump()


class BaseFrozen(Base):
  """Base config with frozen fields.

  See https://docs.pydantic.dev/latest/ for documentation on pydantic.
  """

  model_config = pydantic.ConfigDict(
      frozen=True,
      # Do not allow attributes not defined in pydantic model.
      extra='forbid',
      arbitrary_types_allowed=True,
  )
