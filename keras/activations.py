# Copyright 2015 The TensorFlow Authors. All Rights Reserved.
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
# ==============================================================================
"""Built-in activation functions."""

import sys

import tensorflow.compat.v2 as tf

from keras import backend
import keras.layers.activation as activation_layers
from keras.utils import generic_utils
from tensorflow.python.util.tf_export import keras_export

# b/123041942
# In TF 2.x, if the `tf.nn.softmax` is used as an activation function in Keras
# layers, it gets serialized as 'softmax_v2' instead of 'softmax' as the
# internal method name is returned in serialization. This results in errors in
# model exporting and loading as Keras can't find any activation function with
# the name of `softmax_v2`.
# This dict maps the activation function name from its v2 version to its
# canonical name.
_TF_ACTIVATIONS_V2 = {
    "softmax_v2": "softmax",
}


@keras_export("keras.activations.softmax")
@tf.__internal__.dispatch.add_dispatch_support
def softmax(x, axis=-1):
    """Softmax converts a vector of values to a probability distribution.

    The elements of the output vector are in range (0, 1) and sum to 1.

    Each vector is handled independently. The `axis` argument sets which axis
    of the input the function is applied along.

    Softmax is often used as the activation for the last
    layer of a classification network because the result could be interpreted as
    a probability distribution.

    The softmax of each vector x is computed as
    `exp(x) / tf.reduce_sum(exp(x))`.

    The input values in are the log-odds of the resulting probability.

    Args:
      x : Input tensor.
      axis: Integer, axis along which the softmax normalization is applied.

    Returns:
      Tensor, output of softmax transformation (all values are non-negative
        and sum to 1).

    Examples:

    **Example 1: standalone usage**

    >>> inputs = tf.random.normal(shape=(32, 10))
    >>> outputs = tf.keras.activations.softmax(inputs)
    >>> tf.reduce_sum(outputs[0, :])  # Each sample in the batch now sums to 1
    <tf.Tensor: shape=(), dtype=float32, numpy=1.0000001>

    **Example 2: usage in a `Dense` layer**

    >>> layer = tf.keras.layers.Dense(32, activation=tf.keras.activations.softmax)
    """
    if x.shape.rank > 1:
        if isinstance(axis, int):
            output = tf.nn.softmax(x, axis=axis)
        else:
            # nn.softmax does not support tuple axis.
            e = tf.exp(x - tf.reduce_max(x, axis=axis, keepdims=True))
            s = tf.reduce_sum(e, axis=axis, keepdims=True)
            output = e / s
    else:
        raise ValueError(
            "Cannot apply softmax to a tensor that is 1D. "
            f"Received input: {x}"
        )

    # Cache the logits to use for crossentropy loss.
    output._keras_logits = x  # pylint: disable=protected-access
    return output


@keras_export("keras.activations.elu")
@tf.__internal__.dispatch.add_dispatch_support
def elu(x, alpha=1.0):
    """Exponential Linear Unit.

    The exponential linear unit (ELU) with `alpha > 0` is:
    `x` if `x > 0` and
    `alpha * (exp(x) - 1)` if `x < 0`
    The ELU hyperparameter `alpha` controls the value to which an
    ELU saturates for negative net inputs. ELUs diminish the
    vanishing gradient effect.

    ELUs have negative values which pushes the mean of the activations
    closer to zero.
    Mean activations that are closer to zero enable faster learning as they
    bring the gradient closer to the natural gradient.
    ELUs saturate to a negative value when the argument gets smaller.
    Saturation means a small derivative which decreases the variation
    and the information that is propagated to the next layer.

    Example Usage:

    >>> import tensorflow as tf
    >>> model = tf.keras.Sequential()
    >>> model.add(tf.keras.layers.Conv2D(32, (3, 3), activation='elu',
    ...          input_shape=(28, 28, 1)))
    >>> model.add(tf.keras.layers.MaxPooling2D((2, 2)))
    >>> model.add(tf.keras.layers.Conv2D(64, (3, 3), activation='elu'))
    >>> model.add(tf.keras.layers.MaxPooling2D((2, 2)))
    >>> model.add(tf.keras.layers.Conv2D(64, (3, 3), activation='elu'))

    <tensorflow.python.keras.engine.sequential.Sequential object ...>

    Args:
        x: Input tensor.
        alpha: A scalar, slope of negative section. `alpha` controls the value to
          which an ELU saturates for negative net inputs.

    Returns:
        The exponential linear unit (ELU) activation function: `x` if `x > 0` and
        `alpha * (exp(x) - 1)` if `x < 0`.


    Reference:
        [Fast and Accurate Deep Network Learning by Exponential Linear Units
        (ELUs) (Clevert et al, 2016)](https://arxiv.org/abs/1511.07289)
    """
    return backend.elu(x, alpha)


@keras_export("keras.activations.selu")
@tf.__internal__.dispatch.add_dispatch_support
def selu(x):
    """Scaled Exponential Linear Unit (SELU).

    The Scaled Exponential Linear Unit (SELU) activation function is defined as:

    - `if x > 0: return scale * x`
    - `if x < 0: return scale * alpha * (exp(x) - 1)`

    where `alpha` and `scale` are pre-defined constants
    (`alpha=1.67326324` and `scale=1.05070098`).

    Basically, the SELU activation function multiplies `scale` (> 1) with the
    output of the `tf.keras.activations.elu` function to ensure a slope larger
    than one for positive inputs.

    The values of `alpha` and `scale` are
    chosen so that the mean and variance of the inputs are preserved
    between two consecutive layers as long as the weights are initialized
    correctly (see `tf.keras.initializers.LecunNormal` initializer)
    and the number of input units is "large enough"
    (see reference paper for more information).

    Example Usage:

    >>> num_classes = 10  # 10-class problem
    >>> model = tf.keras.Sequential()
    >>> model.add(tf.keras.layers.Dense(64, kernel_initializer='lecun_normal',
    ...                                 activation='selu'))
    >>> model.add(tf.keras.layers.Dense(32, kernel_initializer='lecun_normal',
    ...                                 activation='selu'))
    >>> model.add(tf.keras.layers.Dense(16, kernel_initializer='lecun_normal',
    ...                                 activation='selu'))
    >>> model.add(tf.keras.layers.Dense(num_classes, activation='softmax'))

    Args:
        x: A tensor or variable to compute the activation function for.

    Returns:
        The scaled exponential unit activation: `scale * elu(x, alpha)`.

    Notes:
        - To be used together with the
          `tf.keras.initializers.LecunNormal` initializer.
        - To be used together with the dropout variant
          `tf.keras.layers.AlphaDropout` (not regular dropout).

    References:
        - [Klambauer et al., 2017](https://arxiv.org/abs/1706.02515)
    """
    return tf.nn.selu(x)


@keras_export("keras.activations.softplus")
@tf.__internal__.dispatch.add_dispatch_support
def softplus(x):
    """Softplus activation function, `softplus(x) = log(exp(x) + 1)`.

    Example Usage:

    >>> a = tf.constant([-20, -1.0, 0.0, 1.0, 20], dtype = tf.float32)
    >>> b = tf.keras.activations.softplus(a)
    >>> b.numpy()
    array([2.0611537e-09, 3.1326166e-01, 6.9314718e-01, 1.3132616e+00,
             2.0000000e+01], dtype=float32)

    Args:
        x: Input tensor.

    Returns:
        The softplus activation: `log(exp(x) + 1)`.
    """
    return tf.math.softplus(x)


@keras_export("keras.activations.softsign")
@tf.__internal__.dispatch.add_dispatch_support
def softsign(x):
    """Softsign activation function, `softsign(x) = x / (abs(x) + 1)`.

    Example Usage:

    >>> a = tf.constant([-1.0, 0.0, 1.0], dtype = tf.float32)
    >>> b = tf.keras.activations.softsign(a)
    >>> b.numpy()
    array([-0.5,  0. ,  0.5], dtype=float32)

    Args:
        x: Input tensor.

    Returns:
        The softsign activation: `x / (abs(x) + 1)`.
    """
    return tf.math.softsign(x)


@keras_export("keras.activations.swish")
@tf.__internal__.dispatch.add_dispatch_support
def swish(x):
    """Swish activation function, `swish(x) = x * sigmoid(x)`.

    Swish activation function which returns `x*sigmoid(x)`.
    It is a smooth, non-monotonic function that consistently matches
    or outperforms ReLU on deep networks, it is unbounded above and
    bounded below.


    Example Usage:

    >>> a = tf.constant([-20, -1.0, 0.0, 1.0, 20], dtype = tf.float32)
    >>> b = tf.keras.activations.swish(a)
    >>> b.numpy()
    array([-4.1223075e-08, -2.6894143e-01,  0.0000000e+00,  7.3105860e-01,
              2.0000000e+01], dtype=float32)

    Args:
        x: Input tensor.

    Returns:
        The swish activation applied to `x` (see reference paper for details).

    Reference:
      - [Ramachandran et al., 2017](https://arxiv.org/abs/1710.05941)
    """
    return tf.nn.silu(x)


@keras_export("keras.activations.relu")
@tf.__internal__.dispatch.add_dispatch_support
def relu(x, alpha=0.0, max_value=None, threshold=0.0):
    """Applies the rectified linear unit activation function.

    With default values, this returns the standard ReLU activation:
    `max(x, 0)`, the element-wise maximum of 0 and the input tensor.

    Modifying default parameters allows you to use non-zero thresholds,
    change the max value of the activation,
    and to use a non-zero multiple of the input for values below the threshold.

    For example:

    >>> foo = tf.constant([-10, -5, 0.0, 5, 10], dtype = tf.float32)
    >>> tf.keras.activations.relu(foo).numpy()
    array([ 0.,  0.,  0.,  5., 10.], dtype=float32)
    >>> tf.keras.activations.relu(foo, alpha=0.5).numpy()
    array([-5. , -2.5,  0. ,  5. , 10. ], dtype=float32)
    >>> tf.keras.activations.relu(foo, max_value=5.).numpy()
    array([0., 0., 0., 5., 5.], dtype=float32)
    >>> tf.keras.activations.relu(foo, threshold=5.).numpy()
    array([-0., -0.,  0.,  0., 10.], dtype=float32)

    Args:
        x: Input `tensor` or `variable`.
        alpha: A `float` that governs the slope for values lower than the
          threshold.
        max_value: A `float` that sets the saturation threshold (the largest value
          the function will return).
        threshold: A `float` giving the threshold value of the activation function
          below which values will be damped or set to zero.

    Returns:
        A `Tensor` representing the input tensor,
        transformed by the relu activation function.
        Tensor will be of the same shape and dtype of input `x`.
    """
    return backend.relu(
        x, alpha=alpha, max_value=max_value, threshold=threshold
    )


@keras_export("keras.activations.gelu", v1=[])
@tf.__internal__.dispatch.add_dispatch_support
def gelu(x, approximate=False):
    """Applies the Gaussian error linear unit (GELU) activation function.

    Gaussian error linear unit (GELU) computes
    `x * P(X <= x)`, where `P(X) ~ N(0, 1)`.
    The (GELU) nonlinearity weights inputs by their value, rather than gates
    inputs by their sign as in ReLU.

    For example:

    >>> x = tf.constant([-3.0, -1.0, 0.0, 1.0, 3.0], dtype=tf.float32)
    >>> y = tf.keras.activations.gelu(x)
    >>> y.numpy()
    array([-0.00404951, -0.15865529,  0.        ,  0.8413447 ,  2.9959507 ],
        dtype=float32)
    >>> y = tf.keras.activations.gelu(x, approximate=True)
    >>> y.numpy()
    array([-0.00363752, -0.15880796,  0.        ,  0.841192  ,  2.9963627 ],
        dtype=float32)

    Args:
        x: Input tensor.
        approximate: A `bool`, whether to enable approximation.

    Returns:
        The gaussian error linear activation:
        `0.5 * x * (1 + tanh(sqrt(2 / pi) * (x + 0.044715 * x^3)))`
        if `approximate` is `True` or
        `x * P(X <= x) = 0.5 * x * (1 + erf(x / sqrt(2)))`,
        where `P(X) ~ N(0, 1)`,
        if `approximate` is `False`.

    Reference:
      - [Gaussian Error Linear Units (GELUs)](https://arxiv.org/abs/1606.08415)
    """
    return tf.nn.gelu(x, approximate)


@keras_export("keras.activations.tanh")
@tf.__internal__.dispatch.add_dispatch_support
def tanh(x):
    """Hyperbolic tangent activation function.

    For example:

    >>> a = tf.constant([-3.0,-1.0, 0.0,1.0,3.0], dtype = tf.float32)
    >>> b = tf.keras.activations.tanh(a)
    >>> b.numpy()
    array([-0.9950547, -0.7615942,  0.,  0.7615942,  0.9950547], dtype=float32)

    Args:
        x: Input tensor.

    Returns:
        Tensor of same shape and dtype of input `x`, with tanh activation:
        `tanh(x) = sinh(x)/cosh(x) = ((exp(x) - exp(-x))/(exp(x) + exp(-x)))`.
    """
    return tf.tanh(x)


@keras_export("keras.activations.sigmoid")
@tf.__internal__.dispatch.add_dispatch_support
def sigmoid(x):
    """Sigmoid activation function, `sigmoid(x) = 1 / (1 + exp(-x))`.

    Applies the sigmoid activation function. For small values (<-5),
    `sigmoid` returns a value close to zero, and for large values (>5)
    the result of the function gets close to 1.

    Sigmoid is equivalent to a 2-element Softmax, where the second element is
    assumed to be zero. The sigmoid function always returns a value between
    0 and 1.

    For example:

    >>> a = tf.constant([-20, -1.0, 0.0, 1.0, 20], dtype = tf.float32)
    >>> b = tf.keras.activations.sigmoid(a)
    >>> b.numpy()
    array([2.0611537e-09, 2.6894143e-01, 5.0000000e-01, 7.3105860e-01,
             1.0000000e+00], dtype=float32)

    Args:
        x: Input tensor.

    Returns:
        Tensor with the sigmoid activation: `1 / (1 + exp(-x))`.
    """
    output = tf.sigmoid(x)
    # Cache the logits to use for crossentropy loss.
    output._keras_logits = x  # pylint: disable=protected-access
    return output


@keras_export("keras.activations.exponential")
@tf.__internal__.dispatch.add_dispatch_support
def exponential(x):
    """Exponential activation function.

    For example:

    >>> a = tf.constant([-3.0,-1.0, 0.0,1.0,3.0], dtype = tf.float32)
    >>> b = tf.keras.activations.exponential(a)
    >>> b.numpy()
    array([0.04978707,  0.36787945,  1.,  2.7182817 , 20.085537], dtype=float32)

    Args:
        x: Input tensor.

    Returns:
        Tensor with exponential activation: `exp(x)`.
    """
    return tf.exp(x)


@keras_export("keras.activations.hard_sigmoid")
@tf.__internal__.dispatch.add_dispatch_support
def hard_sigmoid(x):
    """Hard sigmoid activation function.

    A faster approximation of the sigmoid activation.
    Piecewise linear approximation of the sigmoid function.
    Ref: 'https://en.wikipedia.org/wiki/Hard_sigmoid'

    For example:

    >>> a = tf.constant([-3.0,-1.0, 0.0,1.0,3.0], dtype = tf.float32)
    >>> b = tf.keras.activations.hard_sigmoid(a)
    >>> b.numpy()
    array([0. , 0.3, 0.5, 0.7, 1. ], dtype=float32)

    Args:
        x: Input tensor.

    Returns:
      The hard sigmoid activation, defined as:

        - `if x < -2.5: return 0`
        - `if x > 2.5: return 1`
        - `if -2.5 <= x <= 2.5: return 0.2 * x + 0.5`
    """
    return backend.hard_sigmoid(x)


@keras_export("keras.activations.linear")
@tf.__internal__.dispatch.add_dispatch_support
def linear(x):
    """Linear activation function (pass-through).

    For example:

    >>> a = tf.constant([-3.0,-1.0, 0.0,1.0,3.0], dtype = tf.float32)
    >>> b = tf.keras.activations.linear(a)
    >>> b.numpy()
    array([-3., -1.,  0.,  1.,  3.], dtype=float32)

    Args:
        x: Input tensor.

    Returns:
        The input, unmodified.
    """
    return x


@keras_export("keras.activations.serialize")
@tf.__internal__.dispatch.add_dispatch_support
def serialize(activation):
    """Returns the string identifier of an activation function.

    Args:
        activation : Function object.

    Returns:
        String denoting the name attribute of the input function

    For example:

    >>> tf.keras.activations.serialize(tf.keras.activations.tanh)
    'tanh'
    >>> tf.keras.activations.serialize(tf.keras.activations.sigmoid)
    'sigmoid'
    >>> tf.keras.activations.serialize('abcd')
    Traceback (most recent call last):
    ...
    ValueError: ('Cannot serialize', 'abcd')

    Raises:
        ValueError: The input function is not a valid one.
    """
    if (
        hasattr(activation, "__name__")
        and activation.__name__ in _TF_ACTIVATIONS_V2
    ):
        return _TF_ACTIVATIONS_V2[activation.__name__]
    return generic_utils.serialize_keras_object(activation)


# Add additional globals so that deserialize can find these common activation
# functions
leaky_relu = tf.nn.leaky_relu
log_softmax = tf.nn.log_softmax
relu6 = tf.nn.relu6
silu = tf.nn.silu


@keras_export("keras.activations.deserialize")
@tf.__internal__.dispatch.add_dispatch_support
def deserialize(name, custom_objects=None):
    """Returns activation function given a string identifier.

    Args:
      name: The name of the activation function.
      custom_objects: Optional `{function_name: function_obj}`
        dictionary listing user-provided activation functions.

    Returns:
        Corresponding activation function.

    For example:

    >>> tf.keras.activations.deserialize('linear')
     <function linear at 0x1239596a8>
    >>> tf.keras.activations.deserialize('sigmoid')
     <function sigmoid at 0x123959510>
    >>> tf.keras.activations.deserialize('abcd')
    Traceback (most recent call last):
    ...
    ValueError: Unknown activation function:abcd

    Raises:
        ValueError: `Unknown activation function` if the input string does not
        denote any defined Tensorflow activation function.
    """
    activation_functions = {}
    current_module = sys.modules[__name__]

    # we put 'current_module' after 'activation_layers' to prefer the local one
    # if there is a collision
    generic_utils.populate_dict_with_module_objects(
        activation_functions,
        (activation_layers, current_module),
        obj_filter=callable,
    )

    return generic_utils.deserialize_keras_object(
        name,
        module_objects=activation_functions,
        custom_objects=custom_objects,
        printable_module_name="activation function",
    )


@keras_export("keras.activations.get")
@tf.__internal__.dispatch.add_dispatch_support
def get(identifier):
    """Returns function.

    Args:
        identifier: Function or string

    Returns:
        Function corresponding to the input string or input function.

    For example:

    >>> tf.keras.activations.get('softmax')
     <function softmax at 0x1222a3d90>
    >>> tf.keras.activations.get(tf.keras.activations.softmax)
     <function softmax at 0x1222a3d90>
    >>> tf.keras.activations.get(None)
     <function linear at 0x1239596a8>
    >>> tf.keras.activations.get(abs)
     <built-in function abs>
    >>> tf.keras.activations.get('abcd')
    Traceback (most recent call last):
    ...
    ValueError: Unknown activation function:abcd

    Raises:
        ValueError: Input is an unknown function or string, i.e., the input does
        not denote any defined function.
    """
    if identifier is None:
        return linear
    if isinstance(identifier, (str, dict)):
        return deserialize(identifier)
    elif callable(identifier):
        return identifier
    else:
        raise TypeError(
            f"Could not interpret activation function identifier: {identifier}"
        )
