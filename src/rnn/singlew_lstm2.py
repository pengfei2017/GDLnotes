# coding=utf-8

import numpy as np
import tensorflow as tf

MAX_DATA_SIZE = 1000000


def logprob(predictions, labels):
    # prevent negative probability
    """Log-probability of the true labels in a predicted batch."""
    predictions[predictions < 1e-10] = 1e-10
    return np.sum(np.multiply(labels, -np.log(predictions))) / labels.shape[0]


def raw_data():
    return [1.0 / (i + 1) for i in range(MAX_DATA_SIZE)]


def piece_data(raw_data, i, piece_size):
    return raw_data[piece_size * i: piece_size * (i + 1)]


def piece_label(raw_data, i, piece_size):
    return raw_data[piece_size * i + 1: piece_size * (i + 1) + 1]


def data_idx():
    return [i for i in range(MAX_DATA_SIZE / 100 * 9)], [j + MAX_DATA_SIZE / 100 * 9 for j in range(MAX_DATA_SIZE / 100)]
    # return [i for i in range(900)], [j + 90 for j in range(100)]


class TrainBatch(object):
    def __init__(self):
        self.cur_idx = 0
        self.cur_test_idx = 0
        self.raw = raw_data()
        self.train_idxs, test_idxs = data_idx()
        self.X_train = [piece_data(raw, i, batch_size) for i in self.train_idxs]
        self.y_train = [piece_label(raw, i, batch_size) for i in self.train_idxs]
        self.X_test = [piece_data(raw, i, batch_size) for i in test_idxs]
        self.y_test = [piece_label(raw, i, batch_size) for i in test_idxs]

    def next_train(self):
        self.cur_idx += 1
        cur_train_data = np.array(
            self.X_train[batch_cnt_per_step * (self.cur_idx - 1): batch_cnt_per_step * self.cur_idx])
        cur_train_label = np.array(
            self.y_train[batch_cnt_per_step * (self.cur_idx - 1): batch_cnt_per_step * self.cur_idx])
        print(cur_train_data.shape)
        print(cur_train_label.shape)
        print(self.cur_idx)
        return cur_train_data.reshape((batch_cnt_per_step, batch_size, vocabulary_size)), \
            cur_train_label.reshape((batch_cnt_per_step, batch_size, vocabulary_size))

    def next_test(self):
        self.cur_test_idx += 1
        cur_train_data = np.array(
            self.X_test[batch_cnt_per_step * (self.cur_test_idx - 1): batch_cnt_per_step * self.cur_test_idx])
        cur_train_label = np.array(
            self.y_test[batch_cnt_per_step * (self.cur_test_idx - 1): batch_cnt_per_step * self.cur_test_idx])
        print(cur_train_data.shape)
        print(cur_train_label.shape)
        print(self.cur_test_idx)
        return cur_train_data.reshape((batch_cnt_per_step, batch_size, vocabulary_size)), \
               cur_train_label.reshape((batch_cnt_per_step, batch_size, vocabulary_size))



# Parameters

training_steps = 3000

# Network Parameters
# 每次训练10条数据
batch_cnt_per_step = 10
batch_size = 10  # 10 num to predict one num
n_hidden = 128  # hidden layer num of features
EMBEDDING_SIZE = 128

# hyperbola data
raw = raw_data()

# Simple LSTM Model.
num_nodes = 64
vocabulary_size = 1
train_batch = TrainBatch()

graph = tf.Graph()
with graph.as_default():
    # Parameters:
    # Input, Forget, Memory, Output gate: input, previous output, and bias.
    ifcox = tf.Variable(tf.truncated_normal([vocabulary_size, num_nodes * 4], -0.1, 0.1))
    ifcom = tf.Variable(tf.truncated_normal([num_nodes, num_nodes * 4], -0.1, 0.1))
    ifcob = tf.Variable(tf.zeros([1, num_nodes * 4]))

    # Variables saving state across unrollings.
    saved_output = tf.Variable(tf.zeros([batch_size, num_nodes]), trainable=False)
    saved_state = tf.Variable(tf.zeros([batch_size, num_nodes]), trainable=False)
    # Classifier weights and biases.
    w = tf.Variable(tf.truncated_normal([num_nodes, vocabulary_size], -0.1, 0.1))
    b = tf.Variable(tf.zeros([vocabulary_size]))


    def _slice(_x, n, dim):
        return _x[:, n * dim:(n + 1) * dim]


    # Definition of the cell computation.
    def lstm_cell(cur_input, last_output, last_state):
        ifco_gates = tf.matmul(cur_input, ifcox) + tf.matmul(last_output, ifcom) + ifcob
        input_gate = tf.sigmoid(_slice(ifco_gates, 0, num_nodes))
        forget_gate = tf.sigmoid(_slice(ifco_gates, 1, num_nodes))
        update = _slice(ifco_gates, 2, num_nodes)
        last_state = forget_gate * last_state + input_gate * tf.tanh(update)
        output_gate = tf.sigmoid(_slice(ifco_gates, 3, num_nodes))
        return output_gate * tf.tanh(last_state), last_state


    # Input data.
    train_inputs = [tf.placeholder(tf.float32, shape=[batch_size, vocabulary_size]) for _ in range(batch_cnt_per_step)]
    train_labels = [tf.placeholder(tf.float32, shape=[batch_size, vocabulary_size]) for _ in range(batch_cnt_per_step)]
    # print('#######', train_inputs)
    # print('#######', train_labels)

    # Unrolled LSTM loop.
    outputs = list()
    output = saved_output
    state = saved_state
    #######################################################################################
    # This is multi lstm layer
    for i in train_inputs:
        output, state = lstm_cell(i, output, state)
        outputs.append(output)
    #######################################################################################

    # State saving
    with tf.control_dependencies([saved_output.assign(output),
                                  saved_state.assign(state)]):
        # Classifier.
        logits = tf.nn.xw_plus_b(tf.concat(0, outputs), w, b)
        loss = tf.reduce_mean(
            tf.nn.softmax_cross_entropy_with_logits(
                logits, tf.concat(0, train_labels)))

    # Optimizer.
    global_step = tf.Variable(0)
    learning_rate = tf.train.exponential_decay(
        10.0, global_step, 5000, 0.1, staircase=True)
    optimizer = tf.train.GradientDescentOptimizer(learning_rate)
    gradients, v = zip(*optimizer.compute_gradients(loss))
    gradients, _ = tf.clip_by_global_norm(gradients, 1.25)
    optimizer = optimizer.apply_gradients(
        zip(gradients, v), global_step=global_step)

    # Predictions, not softmax for no label
    train_prediction = logits

    # Sampling and validation eval: batch 1, no unrolling.
    sample_input = tf.placeholder(tf.float32, shape=[batch_cnt_per_step, vocabulary_size])
    saved_sample_output = tf.Variable(tf.zeros([batch_cnt_per_step, num_nodes]))
    saved_sample_state = tf.Variable(tf.zeros([batch_cnt_per_step, num_nodes]))
    reset_sample_state = tf.group(
        saved_sample_output.assign(tf.zeros([batch_cnt_per_step, num_nodes])),
        saved_sample_state.assign(tf.zeros([batch_cnt_per_step, num_nodes])))
    sample_output, sample_state = lstm_cell(
        sample_input, saved_sample_output, saved_sample_state)
    with tf.control_dependencies([saved_sample_output.assign(sample_output),
                                  saved_sample_state.assign(sample_state)]):
        sample_prediction = tf.nn.xw_plus_b(sample_output, w, b)

num_steps = 7000  # 上限900
sum_freq = 100

with tf.Session(graph=graph) as session:
    tf.initialize_all_variables().run()
    print('Initialized')
    mean_loss = 0
    for step in range(num_steps):
        # prepare and feed train data
        input_s, label_s = train_batch.next_train()
        feed_dict = dict()
        for i in range(batch_cnt_per_step):
            feed_dict[train_inputs[i]] = input_s[i]
        for i in range(batch_cnt_per_step):
            feed_dict[train_labels[i]] = label_s[i]

        # train
        _, l, predictions, lr = session.run(
            [optimizer, loss, train_prediction, learning_rate], feed_dict=feed_dict)
        predictions = predictions.reshape((10, 10, 1))
        mean_loss += l
        if step % sum_freq == 0:
            if step > 0:
                mean_loss /= sum_freq
            # The mean loss is an estimate of the loss over the last few batches.
            print(
                'Average loss at step %d: %f learning rate: %f' % (step, mean_loss, lr))
            mean_loss = 0
            print('Minibatch perplexity: %.2f' % float(
                np.exp(logprob(predictions, label_s))))
            if step % (sum_freq * 10) == 0:
                # Generate some samples.
                print('=' * 80)
                feeds, feed_labels = train_batch.next_test()
                for i in range(batch_cnt_per_step):
                    feed = feeds[i]
                    feed_label = feed_labels[i]
                    f_prediction = sample_prediction.eval({sample_input: feed})
                    # print ('label:')
                    # print(feed_label)
                    # print('predict:')
                    # print(f_prediction)
                    print('Minibatch perplexity: %.2f' % float(np.exp(logprob(f_prediction, feed_label))))
                print('=' * 80)
