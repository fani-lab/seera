import numpy as np
import pandas as pd
import pytrec_eval
import os
from datetime import datetime, timedelta
from tqdm import tqdm
import sklearn.metrics.cluster as CM
import matplotlib.pyplot as plt

import Params
from cmn import Common as cmn


def plot(df):
    metrics = list(Params.evl['extrinsicMetrics'])
    step = int(len(df.score) / len(metrics))
    values = {}
    for i in range(len(metrics)):
        values[metrics[i]] = df.score[i * step:(i + 1) * step]
    metric_nums = []
    for i in range(len(metrics)):
        metric_nums.append([])
        metric_nums[-1].append(values[metrics[i]].mean())
        metric_nums[-1].append(values[metrics[i]].std())
    table = pd.DataFrame(metric_nums, index=metrics, columns=['mean', 'std'])
    table.to_csv(f'{Params.apl["path2save"]}/evl/Pred.Eval.Mean.MeanStd.csv', index_label="metric", header=["score"])
    plt.figure(figsize=(15, 10))
    plt.style.use('seaborn')
    for m in metrics:
        plt.plot(range(len(values[m].values)), values[m].values, label=m)
        # v = values[m].values
        # plt.fill_between(range(len(v)), v - v.std(), v + v.std(), label=m, alpha=0.2)
    plt.title(Params['general']['baseline'].split('/')[1], fontdict={'fontsize': 32})
    plt.yticks(fontsize=16)
    plt.xticks(fontsize=16)
    plt.legend(loc="upper left", prop={'size': 16})
    plt.savefig(f'{Params.apl["path2save"]}/evl/Pred.Eval.Mean.Chart.png')
def user_mentions():
    # Load News
    news = pd.read_csv(f'{Params.dal["path"]}/News.csv')
    news = news[news[Params.apl["textTitle"]].notna()]

    # Load Tweets
    tweets = pd.read_csv(f'{Params.dal["path"]}/Tweets.csv')

    ### Run the following section if evaluation should be done on only last time interval news articles ###
    # eval_start = datetime.strptime(Params.dal['end'], f'%Y-%m-%d') - timedelta(days=Params.dal['timeInterval'] - 1)  # May need changes for new news dataset
    # eval_start = eval_start.strftime('%Y-%m-%d') + ' 00:00:00'
    # eval_end = Params.dal['end'] + ' 24:00:00'
    # tweets = tweets[tweets['CreationTimestamp'] >= eval_start]
    # tweets = tweets[tweets['CreationTimestamp'] <= eval_end]

    users = np.load(f'{Params.uml["path2save"]}/Users.npy')
    tweets = tweets[tweets['UserId'].isin(users)]

    # Load Tweet Entities
    tweet_entities = pd.read_csv(f'{Params.dal["path"]}/TweetEntities.csv')
    tweet_entities = tweet_entities[tweet_entities['TweetId'].notna()]
    tweet_entities = tweet_entities[tweet_entities['ExpandedUrl'].notna()]
    tweet_entities = tweet_entities[tweet_entities['TweetId'].isin(tweets['Id'])]

    users_news = {}
    for index, row in tqdm(tweet_entities.iterrows(), total=tweet_entities.shape[0]):
        if row['ExpandedUrl'] in news['Url'].values:
            uid = tweets.loc[tweets['Id'] == row['TweetId']]['UserId'].values[0]
            news_id = news[news['Url'] == row['ExpandedUrl']]['Id'].values[0]
            users_news.setdefault(uid, []).append(news_id)
    return users_news

def intrinsic_evaluation(communities, golden_standard, evaluation_metrics=Params.evl['intrinsicMetrics']):
    results = []
    for m in evaluation_metrics:
        if m == 'adjusted_rand': results.append(('adjusted_rand_score', CM.adjusted_rand_score(golden_standard, communities)))
        elif m == 'completeness': results.append(('completeness_score', CM.completeness_score(golden_standard, communities)))
        elif m == 'homogeneity': results.append(('homogeneity_score', CM.homogeneity_score(golden_standard, communities)))
        elif m == 'rand': results.append(('rand_score', CM.rand_score(golden_standard, communities)))
        elif m == 'v_measure': results.append(('v_measure_score', CM.v_measure_score(golden_standard, communities)))
        elif m == 'normalized_mutual_info' or m == 'NMI': results.append(('normalized_mutual_info_score', CM.normalized_mutual_info_score(golden_standard, communities)))
        elif m == 'adjusted_mutual_info' or m == 'AMI': results.append(('adjusted_mutual_info_score', CM.adjusted_mutual_info_score(golden_standard, communities)))
        elif m == 'mutual_info' or m == 'MI': results.append(('mutual_info_score', CM.mutual_info_score(golden_standard, communities)))
        elif m == 'fowlkes_mallows' or m == 'FMI': results.append(('fowlkes_mallows_score', CM.fowlkes_mallows_score(golden_standard, communities)))
        else: continue
    return results


def main(top_recommendation_user):
    if not os.path.isdir(f'{Params.apl["path2save"]}/evl'): os.makedirs(f'{Params.apl["path2save"]}/evl')
    if Params.evl['evaluationType'].lower() == "intrinsic":
        user_communities = np.load(f'{Params.cpl["path2save"]}/PredUserClusters.npy')
        golden_standard = np.load(f'{Params.dal["path"]}/GoldenStandard.npy')
        scores = np.asarray(intrinsic_evaluation(user_communities, golden_standard))
        np.save(f'{Params.apl["path2save"]}/evl/IntrinsicEvaluationResult.npy', scores)
        return scores
    if Params.evl['evaluationType'].lower() == "extrinsic":
        try: users_mentions = pd.read_pickle(f'{Params.apl["path2save"]}/evl/UserMentions.pkl')
        except (FileNotFoundError, EOFError) as e:
            users_mentions = user_mentions()
            pd.to_pickle(users_mentions, f'{Params.apl["path2save"]}/evl/UserMentions.pkl')

        user_intersection = np.intersect1d(np.asarray(list(top_recommendation_user.keys())), np.asarray(list(users_mentions.keys())))
        top_recommendation_mentioner_user = {muser: top_recommendation_user[muser] for muser in user_intersection}
        pd.to_pickle(top_recommendation_mentioner_user, f'{Params.apl["path2save"]}/topRecommendationMentionerUser.pkl')
        users_mentions_mentioner_user = {muser: users_mentions[muser] for muser in user_intersection}
        pd.to_pickle(users_mentions_mentioner_user, f'{Params.apl["path2save"]}/users_mentions_mentioned_user.pkl')

        #users_mentions_mentioner_user {1: [4], 2: [5], ...}
        #new_top_recommendation_mentioner_user {1: array[3,17], 2: array[3,17], ...}

        metrics = set()
        for metric in Params.evl['extrinsicMetrics']: metrics.add(f"{metric}_{','.join([str(i) for i in range(1, Params.apl['topK'] + 1, 1)])}")

        qrel = {}; run={}
        for i, (y, y_) in enumerate(zip(users_mentions_mentioner_user, top_recommendation_mentioner_user)):
            qrel['u' + str(y)] = {'n' + str(idx): 1 for idx in users_mentions_mentioner_user[y]}
            run['u' + str(y)] = {'n' + str(idx): (len(top_recommendation_mentioner_user[y_])-j) for j, idx in enumerate(top_recommendation_mentioner_user[y_])}

        cmn.logger.info(f'Calling pytrec_eval for {Params.evl["extrinsicMetrics"]} at [1:1:{Params.apl["topK"]}] cutoffs ...')
        df = pd.DataFrame.from_dict(pytrec_eval.RelevanceEvaluator(qrel, metrics).evaluate(run)).T
        df.to_csv(f'{Params.apl["path2save"]}/evl/Pred.Eval.csv', float_format='%.15f')

        cmn.logger.info(f'Averaging ...')
        df_mean = df.mean(axis=0).to_frame('mean')
        df_mean.to_csv(f'{Params.apl["path2save"]}/evl/Pred.Eval.Mean.csv', index_label="metric", header=["score"])
        df_std = df.std(axis=0).to_frame('std')
        df_std.to_csv(f'{Params.apl["path2save"]}/evl/Pred.Eval.Std.csv', index_label="metric", header=["score"])

        cmn.logger.info(f'Plotting ...')
        plot(df_mean)