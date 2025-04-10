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
from typing import Any

from absl.testing import absltest
from absl.testing import parameterized
import numpy as np
from torax.sources import base
from torax.sources import bootstrap_current_source
from torax.sources import fusion_heat_source
from torax.sources import gas_puff_source
from torax.sources import generic_current_source
from torax.sources import pydantic_model
from torax.sources import qei_source
from torax.sources import runtime_params as source_runtime_params_lib
from torax.sources import source_models as source_models_lib
from torax.sources.impurity_radiation_heat_sink import impurity_radiation_constant_fraction
from torax.sources.impurity_radiation_heat_sink import impurity_radiation_mavrin_fit
from torax.torax_pydantic import torax_pydantic


class PydanticModelTest(parameterized.TestCase):

  @parameterized.parameters(
      dict(
          config={
              'gas_puff_source': {
                  'puff_decay_length': 0.3,
                  'S_puff_tot': 0.0,
              }
          },
          expected_sources_model=gas_puff_source.GasPuffSourceConfig,
      ),
      dict(
          config={
              'j_bootstrap': {
                  'bootstrap_mult': 0.3,
              }
          },
          expected_sources_model=bootstrap_current_source.BootstrapCurrentSourceConfig,
      ),
      dict(
          config={
              'fusion_heat_source': {},
          },
          expected_sources_model=fusion_heat_source.FusionHeatSourceConfig,
      ),
      dict(
          config={
              'impurity_radiation_heat_sink': {
                  'model_function_name': 'impurity_radiation_mavrin_fit'
              },
          },
          expected_sources_model=impurity_radiation_mavrin_fit.ImpurityRadiationHeatSinkMavrinFitConfig,
      ),
      dict(
          config={
              'impurity_radiation_heat_sink': {
                  'model_function_name': 'radially_constant_fraction_of_Pin'
              },
          },
          expected_sources_model=impurity_radiation_constant_fraction.ImpurityRadiationHeatSinkConstantFractionConfig,
      ),
  )
  def test_correct_source_model(
      self,
      config: dict[str, Any],
      expected_sources_model: type[base.SourceModelBase],
  ):
    sources_model = pydantic_model.Sources.from_dict(config)
    self.assertIsInstance(
        sources_model.source_model_config[list(config.keys())[0]],
        expected_sources_model,
    )
    # Check that the 3 default sources are always present.
    for key in [
        bootstrap_current_source.BootstrapCurrentSource.SOURCE_NAME,
        qei_source.QeiSource.SOURCE_NAME,
        generic_current_source.GenericCurrentSource.SOURCE_NAME,
    ]:
      self.assertIn(key, sources_model.source_model_config.keys())

  def test_adding_standard_source_via_config(self):
    """Tests that a source can be added with overriding defaults."""
    sources = pydantic_model.Sources.from_dict({
        'gas_puff_source': {
            'puff_decay_length': 1.23,
        },
        'ohmic_heat_source': {
            'is_explicit': True,
            'mode': 'ZERO',  # turn it off.
        },
    })
    source_models = source_models_lib.SourceModels(sources.source_model_config)
    # The non-standard ones are still off.
    self.assertEqual(
        sources.source_model_config['j_bootstrap'].mode,
        source_runtime_params_lib.Mode.ZERO,
    )
    self.assertEqual(
        sources.source_model_config['generic_current_source'].mode,
        source_runtime_params_lib.Mode.ZERO,
    )
    self.assertEqual(
        sources.source_model_config['qei_source'].mode,
        source_runtime_params_lib.Mode.ZERO,
    )
    # But these new sources have been added.
    self.assertLen(source_models.sources, 5)
    self.assertLen(source_models.standard_sources, 3)
    # With the overriding params.
    gas_puff_config = sources.source_model_config['gas_puff_source']
    self.assertIsInstance(gas_puff_config, gas_puff_source.GasPuffSourceConfig)
    self.assertEqual(
        gas_puff_config.puff_decay_length.get_value(0.0),
        1.23,
    )
    self.assertEqual(
        sources.source_model_config['gas_puff_source'].mode,
        source_runtime_params_lib.Mode.MODEL_BASED,  # On by default.
    )
    self.assertEqual(
        sources.source_model_config['ohmic_heat_source'].mode,
        source_runtime_params_lib.Mode.ZERO,
    )

  def test_empty_source_config_only_has_defaults_turned_off(self):
    """Tests that an empty source config has all sources turned off."""
    sources = pydantic_model.Sources.from_dict({})
    self.assertEqual(
        sources.source_model_config['j_bootstrap'].mode,
        source_runtime_params_lib.Mode.ZERO,
    )
    self.assertEqual(
        sources.source_model_config['generic_current_source'].mode,
        source_runtime_params_lib.Mode.ZERO,
    )
    self.assertEqual(
        sources.source_model_config['qei_source'].mode,
        source_runtime_params_lib.Mode.ZERO,
    )
    self.assertLen(sources.source_model_config, 3)

  def test_adding_a_source_with_prescribed_values(self):
    """Tests that a source can be added with overriding defaults."""
    sources = pydantic_model.Sources.from_dict({
        'generic_current_source': {
            'mode': 'PRESCRIBED',
            'prescribed_values': ((
                np.array([0.0, 1.0, 2.0, 3.0]),
                np.array([0., 0.5, 1.0]),
                np.full([4, 3], 42)
            ),),
        },
        'electron_cyclotron_source': {
            'mode': 'PRESCRIBED',
            'prescribed_values': (
                3.,
                4.,
            ),
        }
    })
    mesh = torax_pydantic.Grid1D(nx=4, dx=0.25)
    torax_pydantic.set_grid(sources, mesh)
    source = sources.source_model_config['generic_current_source']
    self.assertLen(source.prescribed_values, 1)
    self.assertIsInstance(
        source.prescribed_values[0], torax_pydantic.TimeVaryingArray)
    source = sources.source_model_config['electron_cyclotron_source']
    self.assertLen(source.prescribed_values, 2)
    self.assertIsInstance(
        source.prescribed_values[0], torax_pydantic.TimeVaryingArray)
    self.assertIsInstance(
        source.prescribed_values[1], torax_pydantic.TimeVaryingArray)
    value = source.prescribed_values[0].get_value(0.0)
    np.testing.assert_equal(value, 3.)
    value = source.prescribed_values[1].get_value(0.0)
    np.testing.assert_equal(value, 4.)

  def test_bremsstrahlung_and_mavrin_validator_with_bremsstrahlung_zero(self):
    valid_config = {
        'bremsstrahlung_heat_sink': {'mode': 'ZERO'},
        'impurity_radiation_heat_sink': {
            'mode': 'PRESCRIBED',
            'model_function_name': 'impurity_radiation_mavrin_fit',
        },
    }
    pydantic_model.Sources.from_dict(valid_config)

  def test_bremsstrahlung_and_mavrin_validator_with_mavrin_zero(self):
    valid_config = {
        'bremsstrahlung_heat_sink': {'mode': 'PRESCRIBED'},
        'impurity_radiation_heat_sink': {
            'mode': 'ZERO',
            'model_function_name': 'impurity_radiation_mavrin_fit',
        },
    }
    pydantic_model.Sources.from_dict(valid_config)

  def test_bremsstrahlung_and_mavrin_validator_with_constant_fraction(self):
    valid_config = {
        'bremsstrahlung_heat_sink': {'mode': 'PRESCRIBED'},
        'impurity_radiation_heat_sink': {
            'mode': 'PRESCRIBED',
            'model_function_name': 'radially_constant_fraction_of_Pin',
        },
    }
    pydantic_model.Sources.from_dict(valid_config)

  def test_bremsstrahlung_and_mavrin_validator_with_invalid_config(self):
    invalid_config = {
        'bremsstrahlung_heat_sink': {'mode': 'PRESCRIBED'},
        'impurity_radiation_heat_sink': {
            'mode': 'PRESCRIBED',
            'model_function_name': 'impurity_radiation_mavrin_fit',
        },
    }
    with self.assertRaisesRegex(
        ValueError,
        'Both bremsstrahlung_heat_sink and impurity_radiation_heat_sink',
    ):
      pydantic_model.Sources.from_dict(invalid_config)


if __name__ == '__main__':
  absltest.main()
