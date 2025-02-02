# -*- coding: utf-8 -*-
"""TextDocumentClassification.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1_0ycGJ0EgoOYoDVFg6jNugB3MPYF7oa0
"""

!pip install transformers[torch]
!pip install accelatare
!pip install transformers opendatasets
!pip install datasets
!pip install evaluate

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from tqdm.auto import tqdm
import tensorflow as tf
from transformers import BertTokenizer, BertForSequenceClassification,BertTokenizerFast

from sklearn.model_selection import train_test_split

import seaborn as sns
import opendatasets as od
from datasets import load_dataset
import evaluate
import torch
from torch.utils.data import Dataset
from torch import cuda

import json
import csv

def Data_ingestion(path,filename,ext):
  file_path=path+filename
  df=pd.read_csv(file_path)
  data=[]
  for rows in list(df["FileName"]):
    document=rows+".txt"
    try:
      with open(document, 'r') as file:
        data.append(file.read())
    except OSError as e:
      data.append("NaN")
  df["Document"]=pd.DataFrame(data)
  return df

new_df=Data_ingestion("","dummy_csv_dipipe.csv","")

def label(labels1):
  id2label={id:label for id,label in enumerate(labels1)}
  label2id={label:id for id,label in enumerate(labels1)}
  return id2label,label2id

def store_labels(label2id):
  with open('labels.json', 'w') as f:
    f.write(json.dumps(label2id, ensure_ascii=False, indent=4))
  return f

def map_label(df):

  labels = df['DocType'].unique().tolist()
  labels.append("Other")
  NUM_LABELS= len(labels)
  id2label,label2id=label(labels)
  store_labels(label2id)
  df["labels"]=df.DocType.map(lambda x: label2id[x.strip()])
  return df,NUM_LABELS,id2label,label2id

new_df,NUM_LABELS,id2label,label2id=map_label(new_df)

new_df

def split_dataframe(df):
  df1=new_df.sample(frac=1)
  train=df1.filter(['Document', 'DocType'], axis=1).iloc[0:int(0.6*len(df1))]
  valid=df1.filter(['Document', 'DocType'], axis=1).iloc[int(0.6*len(df1)):int(0.8*len(df1))]
  test=df1.filter(['Document', 'DocType'], axis=1).iloc[int(0.8*len(df1)):]
  return train,valid,test

class DataLoader(Dataset):
    def __init__(self, encodings, labels):

        self.encodings = encodings
        self.labels = labels

    def __getitem__(self, idx):

        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        item['labels'] = torch.tensor(self.labels[idx])
        return item


    def __len__(self):

        return len(self.labels)

def Data_Loader(train,valid,test):

  train,valid,test=split_dataframe(new_df)
  train_texts=list(train["Document"])
  valid_texts=list(valid["Document"])
  test_texts=list(test["Document"])

  train_labels=list(train.DocType.map(lambda x: label2id[x]))
  valid_labels=list(valid.DocType.map(lambda x: label2id[x.strip()]))
  test_labels=list(test.DocType.map(lambda x: label2id[x.strip()]))

  tokenizer = BertTokenizerFast.from_pretrained("bert-base-uncased", max_length=512)

  train_encodings = tokenizer((train_texts), truncation=True, padding=True)
  val_encodings  = tokenizer((valid_texts), truncation=True, padding=True)
  test_encodings = tokenizer((test_texts), truncation=True, padding=True)

  train_dataloader = DataLoader(train_encodings, train_labels)
  val_dataloader = DataLoader(val_encodings, valid_labels)
  test_dataset = DataLoader(test_encodings, test_labels)

  return train_dataloader,val_dataloader,test_dataset,tokenizer

def compute_metrics(eval_pred):
    accuracy = evaluate.load("accuracy")
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=1)
    return accuracy.compute(predictions=predictions, references=labels)

def load_model(NUM_LABELS,id2label, label2id):
  device = 'cuda' if cuda.is_available() else 'cpu'
  model = BertForSequenceClassification.from_pretrained("bert-base-uncased", num_labels=NUM_LABELS, id2label=id2label, label2id=label2id)
  model.to(device)
  return model

model=load_model(NUM_LABELS,id2label, label2id)

def training_model():
  training_model.model=load_model(NUM_LABELS,id2label, label2id)
  from transformers import TrainingArguments,Trainer
  training_args = TrainingArguments(
  # The output directory where the model predictions and checkpoints will be written
  output_dir='./TTC4900Model',
  do_train=True,
  do_eval=True,
  #  The number of epochs, defaults to 3.0
  num_train_epochs=3,
  per_device_train_batch_size=16,
  per_device_eval_batch_size=32,
  # Number of steps used for a linear warmup
  warmup_steps=100,
  weight_decay=0.01,
  logging_strategy='steps',
  # TensorBoard log directory
  logging_dir='./multi-class-logs',
  logging_steps=50,
  evaluation_strategy="steps",
  eval_steps=50,
  save_strategy="steps",
  fp16=True,
  load_best_model_at_end=True
 )
  train,valid,test=split_dataframe(new_df)
  train_dataloader,val_dataloader,test_dataset,training_model.tokenizer=Data_Loader(train,valid,test)
  training_model.trainer = Trainer(
  # the pre-trained model that will be fine-tuned
  model=training_model.model,
      # training arguments that we defined above
  args=training_args,
  train_dataset=train_dataloader,
  eval_dataset=val_dataloader,
  compute_metrics= compute_metrics
  )

  t=training_model.trainer.train()
  q=[training_model.trainer.evaluate(eval_dataset=df) for df in [train_dataloader, val_dataloader, test_dataset]]
  s=pd.DataFrame(q, index=["train","val","test"]).iloc[:,:]
  return t,s,training_model.tokenizer

t,s,tokenizer=training_model()

from transformers import pipeline
model_path =  "text-document-classification-model"


def savemodel(model_path):

  #training_model.trainer.save_model(model_path)
  #training_model.tokenizer.save_pretrained(model_path)
  device='cuda'
  model.to(device)
  training_model.trainer.save_model(model_path)
  training_model.tokenizer.save_pretrained(model_path)

def reload_model(model_path):

  device = 'cuda' if cuda.is_available() else 'cpu'
  model = BertForSequenceClassification.from_pretrained(model_path,use_auth_token=True)
  model.to(device)
  tokenizer= BertTokenizerFast.from_pretrained(model_path,use_auth_token=True)
  classifier= pipeline("text-classification", model=model, tokenizer=tokenizer)
  return model,tokenizer,classifier

savemodel(model_path)

model,tokenizer,classifier=reload_model(model_path)

from google.colab import drive
drive.mount('/content/gdrive')

PATH = F"/content/gdrive/MyDrive/TextDocumentClassification/text-document-classification-model"

def predict(text):

    inputs =tokenizer(text, padding=True, truncation=True, max_length=512, return_tensors="pt").to("cuda")
    with torch.no_grad():
      outputs = model(**inputs)
    logits=outputs.logits
    probs = softmax(logits,dim=1)
    scores=[]
    for y in probs:
      scores.append((y.max()).item())
    pred_labels=torch.argmax(probs,dim=1)
    pred_label=[]
    for x in pred_labels:
      pred_label.append(model.config.id2label[x.item()])
    return scores,pred_label

predict(texts)

def classify(inputs):

  header = ['Filename',  'Prob_Score','Doctype']
  data=[]

  f=open('Results.csv', 'w', newline='')
  writer = csv.writer(f)
    # write the header
  writer.writerow(header)
  Prob_Score,Doctype=predict(texts)
  for i in range(len(inputs)):
    data=[inputs[i],str(Prob_Score[i]),str(Doctype[i])]
    writer.writerow(data)

new_df.Document

texts=list(new_df.Document)
print(texts)
classify(texts)

