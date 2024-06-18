import facebook as fb




graph = fb.GraphAPI('EAAYsLDJCjQoBO2ztSL63wmXwMny5WjlzoDig1FoQ2HJDQYKrsfpLQSdyqfZBZBQudwFns74yTJvdZB9WUoObOwoGwHFrftBBTYXlbeNzD2ZBRFdreXXbZBXXiVDnqS3YcOi0ynWcPu6Ibpjqvn1al8jxRGSoTz9txA4RZCTgOKrZBRd4VgAzI85YeTKA3iD1pAntL1T4nfRRc7JVKwGrRPZACpXwwsVUImnn0fIZChsUx')
post = graph.put_photo(image=open('t.jpg', 'rb'), message='test11')
graph.put_object(parent_object=post.get('id'), connection_name="comments", message="еуты")